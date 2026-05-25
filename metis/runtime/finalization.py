"""Final response quality enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metis.quality.runner import QualityGateRunner
from metis.runtime.strict_output import StrictOutput


@dataclass(frozen=True)
class FinalizationResult:
    passed: bool
    status: str
    verified: bool = False
    errors: list[str] = field(default_factory=list)
    claim_verifications: list[dict[str, Any]] = field(default_factory=list)


class FinalizationGuard:
    def __init__(
        self,
        quality_runner: QualityGateRunner | None = None,
        evidence_resolver: Any | None = None,
        *,
        require_done_evidence_refs: bool = False,
    ) -> None:
        self.quality_runner = quality_runner or QualityGateRunner()
        self.evidence_resolver = evidence_resolver
        self.require_done_evidence_refs = require_done_evidence_refs

    def validate(
        self,
        *,
        final_text: str,
        artifacts: list[Any] | None = None,
        evidence: list[Any] | None = None,
        tool_results: list[Any] | None = None,
        strict_output: StrictOutput | None = None,
    ) -> FinalizationResult:
        ref_errors = self._validate_strict_refs(strict_output, artifacts or [], evidence or [])
        if ref_errors:
            return FinalizationResult(False, "blocked", False, ref_errors)
        proof_errors = self._validate_done_proof(strict_output)
        if proof_errors:
            return FinalizationResult(False, "blocked", False, proof_errors)
        resolution_errors = self._resolve_strict_evidence_refs(strict_output, evidence or [])
        if resolution_errors:
            return FinalizationResult(False, "blocked", False, resolution_errors)

        result = self.quality_runner.run(
            ["no_fake_completion"],
            {
                "final_text": final_text,
                "artifacts": artifacts or [],
                "evidence": evidence or [],
                "tool_results": tool_results or [],
            },
        )
        if result.passed:
            gate = result.results[0] if result.results else None
            claim_verifications = gate.metadata.get("claim_verifications", []) if gate else []
            return FinalizationResult(True, "final", self._is_verified(strict_output), claim_verifications=claim_verifications)
        failed = result.failed_results
        claim_verifications = []
        for item in failed:
            claim_verifications.extend(item.metadata.get("claim_verifications", []))
        return FinalizationResult(False, "blocked", False, [item.message for item in failed], claim_verifications)

    def _validate_done_proof(self, strict_output: StrictOutput | None) -> list[str]:
        if not self.require_done_evidence_refs or strict_output is None or strict_output.status != "done":
            return []
        if not strict_output.evidence_refs:
            return ["Strict done output requires at least one evidence ref"]
        return []

    @staticmethod
    def _is_verified(strict_output: StrictOutput | None) -> bool:
        if strict_output is None or strict_output.status != "done":
            return False
        return bool(strict_output.evidence_refs)

    def _resolve_strict_evidence_refs(self, strict_output: StrictOutput | None, evidence: list[Any]) -> list[str]:
        if strict_output is None or self.evidence_resolver is None:
            return []
        by_id = {_item_id(item): item for item in evidence if _has_id(item)}
        errors: list[str] = []
        for ref in strict_output.evidence_refs:
            record = by_id.get(ref)
            if record is None:
                continue
            resolution = self.evidence_resolver.resolve(record)
            if not resolution.passed:
                errors.append(f"Unresolved evidence ref {ref}: {resolution.reason}")
        return errors

    @staticmethod
    def _validate_strict_refs(
        strict_output: StrictOutput | None,
        artifacts: list[Any],
        evidence: list[Any],
    ) -> list[str]:
        if strict_output is None:
            return []
        errors: list[str] = []
        artifact_ids = {_item_id(item) for item in artifacts if _has_id(item)}
        evidence_ids = {_item_id(item) for item in evidence if _has_id(item)}
        missing_artifacts = [ref for ref in strict_output.artifact_refs if ref not in artifact_ids]
        missing_evidence = [ref for ref in strict_output.evidence_refs if ref not in evidence_ids]
        if missing_artifacts:
            errors.append(f"Missing artifact refs in final output: {', '.join(missing_artifacts)}")
        if missing_evidence:
            errors.append(f"Missing evidence refs in final output: {', '.join(missing_evidence)}")
        return errors


def _has_id(item: Any) -> bool:
    return bool(_item_id(item))


def _item_id(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("id", ""))
    return str(getattr(item, "id", ""))
