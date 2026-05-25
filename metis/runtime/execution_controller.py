"""Stateful step execution controller."""

from __future__ import annotations

from dataclasses import dataclass

from metis.planning.models import Goal, Step
from metis.planning.task_contract import build_task_contract
from metis.prompts.assembler import PromptAssembler, PromptParts
from metis.quality.runner import QualityGateRunner
from metis.runtime.loop import AgentLoop
from metis.runtime.response import AgentRunRequest, AgentRunResult
from metis.runtime.status import RuntimeStatus


@dataclass
class StepExecutionResult:
    step_id: str
    status: str
    run_result: AgentRunResult
    verified: bool
    reason: str = ""


class ExecutionController:
    """Run one persisted plan step through the AgentLoop."""

    def __init__(
        self,
        *,
        loop: AgentLoop,
        state,
        prompt_assembler: PromptAssembler | None = None,
        quality_runner: QualityGateRunner | None = None,
        artifact_store=None,
        evidence_ledger=None,
        model_profile: str = "small",
    ) -> None:
        self.loop = loop
        self.state = state
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.quality_runner = quality_runner or QualityGateRunner()
        self.artifact_store = artifact_store
        self.evidence_ledger = evidence_ledger
        self.model_profile = model_profile

    async def run_step(
        self,
        *,
        session_id: str,
        goal: Goal,
        step: Step,
        user_message: str | None = None,
        max_turns: int = 12,
    ) -> StepExecutionResult:
        self.state.update_step_status(step.id, "running")
        contract = build_task_contract(
            goal,
            step,
            allowed_tools=step.allowed_tools,
            model_profile=self.model_profile,
        )
        messages = self.prompt_assembler.build(
            PromptParts(
                user_message=user_message or step.action,
                task_contract=contract,
                tool_policy=f"Allowed tools for this step: {', '.join(step.allowed_tools) or '(none)'}",
                strict_output=self.model_profile == "small",
            )
        )
        result = await self.loop.run(
            AgentRunRequest(
                session_id=session_id,
                messages=messages,
                max_turns=max_turns,
                allowed_tools=step.allowed_tools or None,
            )
        )

        verified, reason = self._verify_step(step, result)
        gate_names = step.required_gates
        if verified and gate_names:
            artifacts = self.artifact_store.list_artifacts(session_id) if self.artifact_store else []
            evidence = self.evidence_ledger.list_evidence(session_id) if self.evidence_ledger else []
            quality = self.quality_runner.run(
                gate_names,
                {
                    "session_id": session_id,
                    "step": step,
                    "artifacts": artifacts,
                    "evidence": evidence,
                    "tool_results": result.tool_results,
                    "final_text": result.final_text,
                    "requirements": step.required_inputs + [step.expected_output, step.done_condition],
                },
            )
            verified = quality.passed
            if not quality.passed:
                reason = "; ".join(item.message for item in quality.failed_results)
        final_status = "done" if verified else self._status_for_failed_result(result)
        self.state.update_step_status(step.id, final_status)
        return StepExecutionResult(step.id, final_status, result, verified, reason)

    @staticmethod
    def _verify_step(step: Step, result: AgentRunResult) -> tuple[bool, str]:
        if result.status != "final":
            return False, f"Agent run did not finish: {result.status}"
        if result.errors:
            return False, "; ".join(result.errors)
        if not result.final_text.strip() and not result.tool_results:
            return False, "No final text or tool evidence was produced"
        return True, f"Verified by method: {step.verification_method}"

    @staticmethod
    def _status_for_failed_result(result: AgentRunResult) -> str:
        if result.status in {RuntimeStatus.BLOCKED.value, RuntimeStatus.NEEDS_MORE_WORK.value}:
            return result.status
        return "failed"
