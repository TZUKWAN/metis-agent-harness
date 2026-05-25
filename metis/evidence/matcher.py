"""Match completion claims against typed supporting evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metis.evidence.schema import CompletionClaim


@dataclass(frozen=True)
class ClaimMatchResult:
    passed: bool
    missing_claims: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    claim_verifications: list[dict[str, Any]] = field(default_factory=list)


class ClaimEvidenceMatcher:
    """Detect completion claims and require successful supporting evidence."""

    claim_patterns = {
        CompletionClaim.GENERATED: (
            "generated",
            "created",
            "written",
            "saved",
            "exported",
            "report generated",
            "file generated",
            "artifact generated",
        ),
        CompletionClaim.RAN: (
            "ran",
            "run completed",
            "executed",
            "command executed",
            "checked",
        ),
        CompletionClaim.TESTED: (
            "tested",
            "tests passed",
            "test passed",
            "pytest passed",
            "verified by tests",
            "all tests pass",
            "all tests passed",
        ),
        CompletionClaim.UPLOADED: (
            "uploaded",
            "pushed",
            "published",
            "synced",
            "uploaded to github",
            "pushed to github",
            "pushed to remote",
        ),
        CompletionClaim.FIXED: (
            "fixed",
            "repaired",
            "patched",
            "resolved",
            "bug fixed",
            "issue fixed",
        ),
    }
    extra_claim_patterns = {
        "verified": ("verified", "validated", "confirmed", "verification passed"),
        "reviewed": ("reviewed", "review complete", "code reviewed", "document reviewed"),
        "called_api": (
            "called api",
            "api called",
            "api was called",
            "api call",
            "called the api",
            "request completed",
            "http request completed",
        ),
        "deployed": ("deployed", "deployment complete", "deployed to"),
        "merged": ("merged", "merged to", "merge complete", "pull request merged"),
        "released": ("released", "published release", "release complete", "release is complete", "gh release"),
    }

    def claims_in_text(self, text: str) -> list[CompletionClaim | str]:
        normalized = text.lower()
        claims: list[CompletionClaim | str] = []
        for claim in CompletionClaim:
            patterns = self.claim_patterns.get(claim, ())
            if claim.value in text or any(pattern in normalized for pattern in patterns):
                claims.append(claim)
        for claim, patterns in self.extra_claim_patterns.items():
            if any(pattern in normalized for pattern in patterns):
                claims.append(claim)
        return claims

    def match(
        self,
        *,
        final_text: str,
        artifacts: list[Any] | None = None,
        evidence: list[Any] | None = None,
        tool_results: list[Any] | None = None,
    ) -> ClaimMatchResult:
        claims = self.claims_in_text(final_text)
        verifications = [
            self._verify_claim(claim, artifacts or [], evidence or [], tool_results or [])
            for claim in claims
        ]
        missing = [item["claim"] for item in verifications if not item["verified"]]
        if missing:
            return ClaimMatchResult(
                False,
                missing,
                [f"Completion claim without evidence: {', '.join(missing)}"],
                verifications,
            )
        return ClaimMatchResult(True, [], ["Completion claims have typed supporting evidence"], verifications)

    def _verify_claim(
        self,
        claim: CompletionClaim | str,
        artifacts: list[Any],
        evidence: list[Any],
        tool_results: list[Any],
    ) -> dict[str, Any]:
        verified = self._claim_has_evidence(claim, artifacts, evidence, tool_results)
        return {
            "claim": claim.value if isinstance(claim, CompletionClaim) else str(claim),
            "verified": verified,
            "required_evidence": self._required_evidence(claim),
        }

    def _claim_has_evidence(
        self,
        claim: CompletionClaim | str,
        artifacts: list[Any],
        evidence: list[Any],
        tool_results: list[Any],
    ) -> bool:
        successful_tools = [item for item in tool_results if self._tool_success(item)]
        successful_evidence = [item for item in evidence if self._evidence_success(item)]
        evidence_text = " ".join(self._evidence_text(item) for item in successful_evidence).lower()
        tool_text = " ".join(self._tool_text(item) for item in successful_tools).lower()
        tool_names = {self._tool_name(item) for item in successful_tools}

        if claim == CompletionClaim.GENERATED:
            return bool(artifacts) or any(name in tool_names for name in ("write_file", "edit_file", "apply_patch")) or any(
                marker in evidence_text for marker in ("artifact", "write", "file modified")
            )
        if claim == CompletionClaim.RAN:
            return bool(successful_tools) or any(marker in evidence_text for marker in ("command", "run", "executed"))
        if claim == CompletionClaim.TESTED:
            return self._has_successful_test_evidence(evidence_text, tool_text, tool_names)
        if claim == CompletionClaim.UPLOADED:
            return any(marker in evidence_text or marker in tool_text for marker in ("git", "github", "upload", "push", "remote"))
        if claim == CompletionClaim.FIXED:
            return any(name in tool_names for name in ("write_file", "edit_file", "apply_patch")) or any(
                marker in evidence_text for marker in ("fixed", "file modified", "patch")
            )
        if claim == "verified":
            return self._has_successful_test_evidence(evidence_text, tool_text, tool_names) or any(
                marker in evidence_text or marker in tool_text for marker in ("verified", "validation", "passed")
            )
        if claim == "reviewed":
            return any(name in tool_names for name in ("read_file", "search", "rg")) or any(
                marker in evidence_text or marker in tool_text for marker in ("reviewed", "inspection", "audit")
            )
        if claim == "called_api":
            return any(name in tool_names for name in ("http_request", "api_call", "run_shell", "run_command")) and any(
                marker in tool_text for marker in ("http", "api", "status", "200", "curl")
            ) or "api" in evidence_text
        if claim == "deployed":
            return any(marker in evidence_text or marker in tool_text for marker in ("deploy", "deployment", "hosting"))
        if claim == "merged":
            return any(marker in evidence_text or marker in tool_text for marker in ("merge", "merged", "pull request", "github"))
        if claim == "released":
            return any(marker in evidence_text or marker in tool_text for marker in ("release", "published", "gh release"))
        return False

    @staticmethod
    def _required_evidence(claim: CompletionClaim | str) -> list[str]:
        claim_value = claim.value if isinstance(claim, CompletionClaim) else str(claim)
        requirements = {
            "verified": ["test, validation, audit, or explicit verification evidence"],
            "reviewed": ["read/search/audit evidence showing the reviewed material"],
            "called_api": ["API/tool/HTTP evidence with status or response metadata"],
            "deployed": ["deployment command, API, or platform evidence"],
            "merged": ["Git/GitHub merge evidence"],
            "released": ["release/publish evidence"],
        }
        return requirements.get(claim_value, ["typed supporting evidence"])

    @staticmethod
    def _has_successful_test_evidence(evidence_text: str, tool_text: str, tool_names: set[str]) -> bool:
        test_markers = ("pytest", "unittest", "test command")
        success_markers = ("passed", "exit_code\": 0", "exit_code': 0", "exit_code=0", "0 failed")
        tool_support = bool({"run_shell", "run_command", "run_test"} & tool_names) and any(
            marker in tool_text for marker in test_markers
        )
        evidence_support = any(marker in evidence_text for marker in test_markers)
        success = any(marker in tool_text or marker in evidence_text for marker in success_markers)
        return (tool_support or evidence_support) and success

    @classmethod
    def _tool_success(cls, item: Any) -> bool:
        status = str(cls._field(item, "status") or "").lower()
        error = cls._field(item, "error")
        metadata = cls._metadata(item)
        exit_code = metadata.get("exit_code")
        if status and status != "ok":
            return False
        if error not in ("", None):
            return False
        if exit_code not in ("", None, 0, "0"):
            return False
        return True

    @classmethod
    def _evidence_success(cls, item: Any) -> bool:
        metadata = cls._metadata(item)
        status = str(metadata.get("status", "")).lower()
        exit_code = metadata.get("exit_code")
        if status and status not in {"ok", "success", "passed"}:
            return False
        if exit_code not in ("", None, 0, "0"):
            return False
        return True

    @staticmethod
    def _field(item: Any, key: str) -> Any:
        if isinstance(item, dict):
            return item.get(key, "")
        return getattr(item, key, "")

    @staticmethod
    def _metadata(item: Any) -> dict[str, Any]:
        metadata = item.get("metadata", {}) if isinstance(item, dict) else getattr(item, "metadata", {})
        return metadata if isinstance(metadata, dict) else {}

    @staticmethod
    def _tool_name(item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get("tool_name") or item.get("name") or "")
        return str(getattr(item, "tool_name", getattr(item, "name", "")))

    @staticmethod
    def _tool_text(item: Any) -> str:
        if isinstance(item, dict):
            return " ".join(str(item.get(key, "")) for key in ("tool_name", "name", "content", "status", "error", "metadata"))
        return " ".join(str(getattr(item, key, "")) for key in ("tool_name", "content", "status", "error", "metadata"))

    @staticmethod
    def _evidence_text(item: Any) -> str:
        if isinstance(item, dict):
            return " ".join(str(item.get(key, "")) for key in ("claim", "source_type", "source_ref", "metadata"))
        return " ".join(str(getattr(item, key, "")) for key in ("claim", "source_type", "source_ref", "metadata"))
