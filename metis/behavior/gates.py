"""Quality gates for behavior-rule post-hoc auditing.

These gates are evaluated during the AgentLoop finalization phase to ensure
that task execution adheres to the user's behavioral contract.
"""

from __future__ import annotations

from typing import Any

from metis.quality.gates import GateResult, GateSpec


def behavior_completeness_gate() -> GateSpec:
    """Factory for the completeness gate (rules 10 + 15).

    Checks whether:
    - Required verification commands were executed
    - Acceptance criteria have evidence
    - All subtasks have been addressed
    """
    def _handler(context: dict[str, Any]) -> GateResult:
        final_text = str(context.get("final_text", ""))
        tool_results = context.get("tool_results", []) or []
        evidence = context.get("evidence", []) or []

        messages: list[str] = []

        # Check for test execution evidence (rule 10: testing is default scope)
        test_executed = any(
            _tool_has_marker(tr, ("pytest", "unittest", "test", "passed", "failed"))
            for tr in tool_results
        )
        if not test_executed and "test" in final_text.lower():
            messages.append("Tests were mentioned but no test execution evidence found")

        # Check for artifact existence claims (rule 15: per-task verification)
        artifacts = context.get("artifacts", []) or []
        artifact_paths = [str(getattr(a, "path", a.get("path", ""))) for a in artifacts]

        # Check if any file-generation claims lack corresponding artifacts
        import re
        generated_claims = re.findall(r"created\s+`?([^`\n]+)`?", final_text, re.IGNORECASE)
        generated_claims += re.findall(r"generated\s+`?([^`\n]+)`?", final_text, re.IGNORECASE)
        missing_artifacts = [
            c for c in generated_claims
            if not any(c.strip() in p or p.endswith(c.strip()) for p in artifact_paths)
        ]
        if missing_artifacts:
            messages.append(f"Artifact claims without evidence: {', '.join(missing_artifacts)}")

        if messages:
            return GateResult(
                "behavior_completeness",
                False,
                "; ".join(messages),
                {
                    "test_executed": test_executed,
                    "missing_artifacts": missing_artifacts,
                    "artifact_count": len(artifacts),
                    "evidence_count": len(evidence),
                },
            )

        return GateResult(
            "behavior_completeness",
            True,
            "Completeness checks passed",
            {
                "test_executed": test_executed,
                "artifact_count": len(artifacts),
                "evidence_count": len(evidence),
            },
        )

    return GateSpec(
        name="behavior_completeness",
        description="Verify testing and artifact evidence are present (rules 10, 15)",
        handler=_handler,
        failure_policy="warn",
    )


def behavior_no_deception_gate() -> GateSpec:
    """Factory for the no-deception gate (rules 12 + 13).

    Checks whether the output contains indicators of fabricated completion:
    - Placeholder phrases (TODO, FIXME, stub, mock data)
    - Claims of completion without corresponding tool results
    - Simulated / fake output markers
    """
    def _handler(context: dict[str, Any]) -> GateResult:
        final_text = str(context.get("final_text", ""))
        tool_results = context.get("tool_results", []) or []
        artifacts = context.get("artifacts", []) or []

        deception_markers: list[str] = []

        # Detect placeholder text
        placeholders = ("TODO", "FIXME", "STUB", "PLACEHOLDER", "mock data", "simulated")
        lower_text = final_text.lower()
        for marker in placeholders:
            if marker.lower() in lower_text:
                deception_markers.append(f"placeholder marker: '{marker}'")

        # Detect simulated / fake claims
        fake_phrases = (
            " simulated ", " fake ", " dummy ", " placeholder ", " pseudo-",
            " for demonstration purposes", " example data only",
        )
        for phrase in fake_phrases:
            if phrase in lower_text:
                deception_markers.append(f"suspicious phrase: '{phrase.strip()}'")

        # Check for completion claims without tool evidence
        completion_claims = ("已完成", "已完成", "done", "completed", "finished", "successfully")
        has_completion_claim = any(c in lower_text for c in completion_claims)
        has_tool_evidence = len(tool_results) > 0 or len(artifacts) > 0
        if has_completion_claim and not has_tool_evidence:
            # Allow simple conversational responses
            if len(final_text) > 200:
                deception_markers.append("completion claim without tool/artifact evidence")

        if deception_markers:
            return GateResult(
                "behavior_no_deception",
                False,
                f"Potential deception detected: {'; '.join(deception_markers)}",
                {
                    "markers": deception_markers,
                    "tool_result_count": len(tool_results),
                    "artifact_count": len(artifacts),
                },
            )

        return GateResult(
            "behavior_no_deception",
            True,
            "No deception markers detected",
            {
                "tool_result_count": len(tool_results),
                "artifact_count": len(artifacts),
            },
        )

    return GateSpec(
        name="behavior_no_deception",
        description="Detect fabricated completion and placeholder content (rules 12, 13)",
        handler=_handler,
        failure_policy="fail",
    )


def behavior_research_verification_gate() -> GateSpec:
    """Factory for the research-verification gate (rule 11).

    Checks whether tasks that likely require external knowledge show evidence
    of research (web search, literature search, doc fetch).
    """
    def _handler(context: dict[str, Any]) -> GateResult:
        final_text = str(context.get("final_text", ""))
        tool_results = context.get("tool_results", []) or []

        # Determine if research was performed
        research_tools = {"web_search", "web_fetch", "literature_search", "search_code", "find_files"}
        research_performed = any(
            _tool_name(tr) in research_tools for tr in tool_results
        )

        # Heuristic: if the text references external facts, URLs, or citations,
        # research is expected
        lower_text = final_text.lower()
        has_external_refs = any(
            marker in lower_text
            for marker in ("http://", "https://", "according to", "research shows", "documentation")
        )

        if has_external_refs and not research_performed:
            return GateResult(
                "behavior_research_verification",
                False,
                "External references found but no research tool evidence recorded",
                {
                    "research_performed": research_performed,
                    "has_external_refs": has_external_refs,
                    "tool_names": [_tool_name(tr) for tr in tool_results],
                },
            )

        return GateResult(
            "behavior_research_verification",
            True,
            "Research verification passed",
            {
                "research_performed": research_performed,
                "has_external_refs": has_external_refs,
            },
        )

    return GateSpec(
        name="behavior_research_verification",
        description="Verify research was performed when external knowledge is needed (rule 11)",
        handler=_handler,
        failure_policy="warn",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("tool_name") or item.get("name") or "")
    return str(getattr(item, "tool_name", getattr(item, "name", "")))


def _tool_has_marker(item: Any, markers: tuple[str, ...]) -> bool:
    """Check if a tool result contains any of the given markers."""
    text = " ".join(str(v) for v in (
        item if isinstance(item, dict) else getattr(item, "__dict__", {})
    ).values())
    return any(m.lower() in text.lower() for m in markers)
