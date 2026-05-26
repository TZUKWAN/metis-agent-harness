"""Quality gate primitives and default gate functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from metis.artifacts import validators
from metis.evidence.matcher import ClaimEvidenceMatcher


GateFunction = Callable[[dict[str, Any]], "GateResult"]


@dataclass(frozen=True)
class GateSpec:
    name: str
    description: str
    handler: GateFunction
    failure_policy: str = "fail"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


def artifact_exists_gate(context: dict[str, Any]) -> GateResult:
    artifacts = context.get("artifacts") or []
    if not artifacts:
        return GateResult(
            "artifact_exists",
            False,
            "No artifacts were provided",
            {"expected_artifacts": [], "missing_artifacts": [], "artifact_count": 0},
        )
    missing = [artifact.path for artifact in artifacts if not validators.exists(artifact).passed]
    if missing:
        return GateResult(
            "artifact_exists",
            False,
            f"Missing artifacts: {', '.join(missing)}",
            {"expected_artifacts": missing, "missing_artifacts": missing, "artifact_count": len(artifacts)},
        )
    return GateResult(
        "artifact_exists",
        True,
        "All artifacts exist",
        {"expected_artifacts": [artifact.path for artifact in artifacts], "artifact_count": len(artifacts)},
    )


def artifact_non_empty_gate(context: dict[str, Any]) -> GateResult:
    artifacts = context.get("artifacts") or []
    if not artifacts:
        return GateResult(
            "artifact_non_empty",
            False,
            "No artifacts were provided",
            {"expected_artifacts": [], "empty_artifacts": [], "artifact_count": 0},
        )
    empty = [artifact.path for artifact in artifacts if not validators.non_empty(artifact).passed]
    if empty:
        return GateResult(
            "artifact_non_empty",
            False,
            f"Empty artifacts: {', '.join(empty)}",
            {"expected_artifacts": empty, "empty_artifacts": empty, "artifact_count": len(artifacts)},
        )
    return GateResult(
        "artifact_non_empty",
        True,
        "All artifacts are non-empty",
        {"expected_artifacts": [artifact.path for artifact in artifacts], "artifact_count": len(artifacts)},
    )


def no_placeholder_gate(context: dict[str, Any]) -> GateResult:
    artifacts = context.get("artifacts") or []
    for artifact in artifacts:
        result = validators.no_placeholder(artifact)
        if not result.passed:
            return GateResult(
                "no_placeholder",
                False,
                f"{artifact.path}: {result.message}",
                {
                    "expected_artifacts": [artifact.path],
                    "placeholder_artifacts": [artifact.path],
                    "placeholder_message": result.message,
                    "artifact_count": len(artifacts),
                },
            )
    return GateResult(
        "no_placeholder",
        True,
        "No placeholder text found",
        {"expected_artifacts": [artifact.path for artifact in artifacts], "artifact_count": len(artifacts)},
    )


def requirements_covered_gate(context: dict[str, Any]) -> GateResult:
    criteria = _requirement_criteria(context)
    requirements = _stable_unique([criterion["text"] for criterion in criteria])
    if not criteria:
        return GateResult("requirements_covered", True, "No explicit requirements to verify")
    evidence = context.get("evidence", []) or []
    artifacts = context.get("artifacts", []) or []
    tool_results = context.get("tool_results", []) or []
    combined = _requirement_combined_text(context)
    missing_criteria = [
        criterion
        for criterion in criteria
        if not _requirement_criterion_covered(
            criterion,
            combined=combined,
            evidence=evidence,
            artifacts=artifacts,
            tool_results=tool_results,
        )
    ]
    missing = _stable_unique([criterion["text"] for criterion in missing_criteria])
    missing_ids = _stable_unique([criterion["id"] for criterion in missing_criteria if criterion.get("id")])
    missing_artifact_paths = _stable_unique(
        [
            criterion["required_artifact_path"]
            for criterion in missing_criteria
            if criterion.get("required_artifact_path")
            and not _has_artifact_path(artifacts, criterion["required_artifact_path"])
        ]
    )
    missing_tools = _stable_unique(
        [
            criterion["required_tool"]
            for criterion in missing_criteria
            if criterion.get("required_tool") and not _has_successful_tool(tool_results, criterion["required_tool"])
        ]
    )
    if missing:
        return GateResult(
            "requirements_covered",
            False,
            f"Missing requirement evidence: {', '.join(missing)}",
            {
                "requirements": requirements,
                "requirement_criteria": criteria,
                "missing_requirements": missing,
                "missing_requirement_ids": missing_ids,
                "missing_artifact_paths": missing_artifact_paths,
                "missing_tools": missing_tools,
                "evidence_count": len(evidence),
                "artifact_count": len(artifacts),
            },
        )
    return GateResult(
        "requirements_covered",
        True,
        "Requirements are covered",
        {
            "requirements": requirements,
            "requirement_criteria": criteria,
            "missing_requirements": [],
            "missing_requirement_ids": [],
            "missing_artifact_paths": [],
            "missing_tools": [],
            "evidence_count": len(evidence),
            "artifact_count": len(artifacts),
        },
    )


def _requirement_criteria(context: dict[str, Any]) -> list[dict[str, Any]]:
    criteria: list[dict[str, Any]] = []
    for index, item in enumerate(context.get("requirements", []) or []):
        text = str(item).strip()
        if text:
            criteria.append({"id": "", "text": text.lower(), "original_text": text, "index": index})
    for index, item in enumerate(context.get("requirement_criteria", []) or []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("requirement") or "").strip()
        required_source_type = str(item.get("required_source_type") or item.get("source_type") or "")
        required_source_ref = str(item.get("required_source_ref") or item.get("source_ref") or "")
        min_strength = str(item.get("min_strength", ""))
        required_artifact_path = str(item.get("required_artifact_path") or item.get("artifact_path") or "")
        required_tool = str(item.get("required_tool") or item.get("tool_name") or "")
        if not any((text, required_source_type, required_source_ref, min_strength, required_artifact_path, required_tool)):
            continue
        criteria.append(
            {
                "id": str(item.get("id", "")),
                "text": text.lower(),
                "original_text": text,
                "index": index,
                "required_source_type": required_source_type,
                "required_source_ref": required_source_ref,
                "min_strength": min_strength,
                "required_artifact_path": required_artifact_path,
                "required_tool": required_tool,
            }
        )
    return criteria


def _requirement_combined_text(context: dict[str, Any]) -> str:
    evidence_text = " ".join(str(item.claim) for item in context.get("evidence", []) or []).lower()
    artifact_text = " ".join(str(item.path) for item in context.get("artifacts", []) or []).lower()
    final_text = str(context.get("final_text", "")).lower()
    return " ".join([evidence_text, artifact_text, final_text])


def _requirement_criterion_covered(
    criterion: dict[str, Any],
    *,
    combined: str,
    evidence: list[Any],
    artifacts: list[Any],
    tool_results: list[Any],
) -> bool:
    if criterion["text"] and criterion["text"] not in combined:
        return False
    required_artifact_path = criterion.get("required_artifact_path", "")
    if required_artifact_path and not _has_artifact_path(artifacts, required_artifact_path):
        return False
    required_tool = criterion.get("required_tool", "")
    if required_tool and not _has_successful_tool(tool_results, required_tool):
        return False
    required_source_type = criterion.get("required_source_type", "")
    required_source_ref = criterion.get("required_source_ref", "")
    min_strength = criterion.get("min_strength", "")
    if not any((required_source_type, required_source_ref, min_strength)):
        return True
    return any(
        _evidence_matches_requirement(
            record,
            required_source_type=required_source_type,
            required_source_ref=required_source_ref,
            min_strength=min_strength,
        )
        for record in evidence
    )


def _has_artifact_path(artifacts: list[Any], required_path: str) -> bool:
    normalized_required = _normalize_path_text(required_path)
    return any(_normalize_path_text(_artifact_path(artifact)).endswith(normalized_required) for artifact in artifacts)


def _artifact_path(artifact: Any) -> str:
    if isinstance(artifact, dict):
        return str(artifact.get("path", ""))
    return str(getattr(artifact, "path", ""))


def _normalize_path_text(value: str) -> str:
    return value.replace("\\", "/")


def _has_successful_tool(tool_results: list[Any], required_tool: str) -> bool:
    return any(_tool_name(result) == required_tool and not _tool_failed(result) for result in tool_results)


def _tool_failed(result: Any) -> bool:
    if isinstance(result, dict):
        return str(result.get("status", "ok")) != "ok" or bool(result.get("error"))
    return bool(getattr(result, "failed", False))


def _evidence_matches_requirement(
    record: Any,
    *,
    required_source_type: str,
    required_source_ref: str,
    min_strength: str,
) -> bool:
    if required_source_type and _evidence_attr(record, "source_type") != required_source_type:
        return False
    if required_source_ref and _evidence_attr(record, "source_ref") != required_source_ref:
        return False
    if min_strength and not _strength_at_least(_evidence_attr(record, "strength"), min_strength):
        return False
    return True


def _evidence_attr(record: Any, key: str) -> str:
    if isinstance(record, dict):
        return str(record.get(key, ""))
    return str(getattr(record, key, ""))


def _strength_at_least(actual: str, minimum: str) -> bool:
    order = {"weak": 0, "medium": 1, "strong": 2}
    if minimum not in order:
        return True
    return order.get(actual, -1) >= order[minimum]


def _stable_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


COMPLETION_CLAIMS = ("generated", "ran", "tested", "uploaded", "fixed")


def no_fake_completion_gate(context: dict[str, Any]) -> GateResult:
    final_text = str(context.get("final_text", ""))
    result = ClaimEvidenceMatcher().match(
        final_text=final_text,
        artifacts=context.get("artifacts") or [],
        evidence=context.get("evidence") or [],
        tool_results=context.get("tool_results") or [],
    )
    if not result.missing_claims and not ClaimEvidenceMatcher().claims_in_text(final_text):
        return GateResult("no_fake_completion", True, "No completion claim detected")
    metadata = {
        "missing_claims": result.missing_claims,
        "claim_verifications": result.claim_verifications,
    }
    if not result.passed:
        return GateResult("no_fake_completion", False, "; ".join(result.messages), metadata)
    return GateResult("no_fake_completion", True, "; ".join(result.messages), metadata)


def run_attestation_verifies_gate(context: dict[str, Any]) -> GateResult:
    from metis.evals.attestation import verify_run_attestation

    target_run_dirs = context.get("target_run_dirs")
    if not isinstance(target_run_dirs, dict) or not target_run_dirs:
        run_dir = context.get("run_dir")
        if run_dir:
            target_run_dirs = {"run": run_dir}
    if not isinstance(target_run_dirs, dict) or not target_run_dirs:
        return GateResult("run_attestation_verifies", False, "No target run directories were provided")
    failures = []
    for label, run_dir in sorted(target_run_dirs.items()):
        failures.extend(f"{label}: {failure}" for failure in verify_run_attestation(run_dir))
    if failures:
        return GateResult("run_attestation_verifies", False, "; ".join(failures), {"failures": failures})
    return GateResult(
        "run_attestation_verifies",
        True,
        "Run attestation verifies for all target run directories",
        {"target_run_dirs": {str(key): str(value) for key, value in target_run_dirs.items()}},
    )


def _claim_has_evidence(claim: str, context: dict[str, Any]) -> bool:
    artifacts = context.get("artifacts") or []
    evidence = context.get("evidence") or []
    tool_results = context.get("tool_results") or []
    evidence_text = " ".join(_evidence_text(item) for item in evidence).lower()
    tool_text = " ".join(_tool_text(item) for item in tool_results).lower()
    tool_names = {_tool_name(item) for item in tool_results}

    if claim == "generated":
        return bool(artifacts) or "artifact" in evidence_text or "write" in evidence_text
    if claim == "ran":
        return bool(tool_results) or "command" in evidence_text or "run" in evidence_text
    if claim == "tested":
        return (
            "run_shell" in tool_names
            and any(marker in tool_text for marker in ("pytest", "passed", "unittest", "test"))
        ) or any(marker in evidence_text for marker in ("pytest", "passed", "test command"))
    if claim == "uploaded":
        return any(marker in evidence_text or marker in tool_text for marker in ("git", "github", "upload", "push"))
    if claim == "fixed":
        return any(name in tool_names for name in ("write_file", "edit_file", "apply_patch")) or any(
            marker in evidence_text for marker in ("fixed", "write", "patch")
        )
    return False


def _tool_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("tool_name") or item.get("name") or "")
    return str(getattr(item, "tool_name", getattr(item, "name", "")))


def _tool_text(item: Any) -> str:
    if isinstance(item, dict):
        return " ".join(str(item.get(key, "")) for key in ("tool_name", "name", "content", "status", "error"))
    return " ".join(str(getattr(item, key, "")) for key in ("tool_name", "content", "status", "error"))


def _evidence_text(item: Any) -> str:
    if isinstance(item, dict):
        return " ".join(str(item.get(key, "")) for key in ("claim", "source_type", "source_ref"))
    return " ".join(str(getattr(item, key, "")) for key in ("claim", "source_type", "source_ref"))


DEFAULT_GATES = {
    "artifact_exists": GateSpec("artifact_exists", "Artifacts must exist", artifact_exists_gate),
    "artifact_non_empty": GateSpec("artifact_non_empty", "Artifacts must be non-empty", artifact_non_empty_gate),
    "no_placeholder": GateSpec("no_placeholder", "Artifacts must not contain placeholder text", no_placeholder_gate),
    "requirements_covered": GateSpec("requirements_covered", "Requirements need evidence", requirements_covered_gate),
    "no_fake_completion": GateSpec("no_fake_completion", "Completion claims need evidence", no_fake_completion_gate),
    "run_attestation_verifies": GateSpec(
        "run_attestation_verifies",
        "Run attestation subjects must match local artifact bytes",
        run_attestation_verifies_gate,
    ),
}
