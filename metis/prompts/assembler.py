"""Prompt assembler for Metis runtime calls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from metis.planning.task_contract import TaskContractV1
from metis.runtime.strict_output import STRICT_OUTPUT_INSTRUCTIONS, STRICT_OUTPUT_INSTRUCTIONS_SOFT


BASE_IDENTITY = (
    "You are Metis Executor, a domain-neutral agent runtime worker. "
    "Follow the current task contract and use tools only when needed."
)

SMALL_MODEL_IDENTITY = (
    "You are Metis Executor. Complete the user's task step by step.\n"
    "Rules:\n"
    "- Use tools to read files, write files, run commands, or search code.\n"
    "- Call one tool at a time. Wait for the result before proceeding.\n"
    "- If a tool call fails, read the error message carefully. Fix the specific issue (wrong path, wrong argument name, missing file) and retry once.\n"
    "- After all tool calls finish, write a short summary of what you did and what changed.\n"
    "- Do NOT repeat the user's request back. Just execute and report.\n"
    "- Do NOT ask for permission. Proceed with the best action.\n"
    "- If the task is impossible with available tools, say so clearly.\n"
    "- When reading a file, use read_file. For large files, use read_file_range with offset and limit.\n"
    "- When searching, use search_code for patterns and find_files for filenames.\n"
    "- When exploring a directory, use list_directory instead of running ls.\n"
    "- Always check file contents with read_file before writing to avoid overwriting important data.\n"
    "- For multi-step changes, plan the steps first, then execute one at a time."
)


@dataclass
class PromptParts:
    user_message: str
    task_contract: str = ""
    memory_context: str = ""
    workspace_context: str = ""
    evidence_summary: str = ""
    artifact_summary: str = ""
    recent_messages: list[dict[str, Any]] = field(default_factory=list)
    tool_policy: str = ""
    strict_output: bool = False
    strict_output_soft: bool = False
    base_identity: str = BASE_IDENTITY


@dataclass(frozen=True)
class PromptLayer:
    """One auditable layer in a model prompt stack."""

    layer_type: str
    content: str
    source: str
    version: str = "v1"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_type": self.layer_type,
            "content": self.content,
            "source": self.source,
            "version": self.version,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "layer_hash": self.layer_hash(),
        }

    def stable_json(self) -> str:
        payload = {
            "layer_type": self.layer_type,
            "content": self.content,
            "source": self.source,
            "version": self.version,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def layer_hash(self) -> str:
        return hashlib.sha256(self.stable_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PromptStack:
    """Ordered, hashable prompt layers for runtime provenance."""

    layers: list[PromptLayer] = field(default_factory=list)

    def enabled_layers(self) -> list[PromptLayer]:
        return [layer for layer in self.layers if layer.enabled and layer.content.strip()]

    def stack_hash(self) -> str:
        payload = [layer.to_dict() for layer in self.enabled_layers()]
        stable = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(stable.encode("utf-8")).hexdigest()

    def to_system_content(self) -> str:
        sections: list[str] = []
        for layer in self.enabled_layers():
            sections.append(f"[{layer.layer_type} | source={layer.source} | hash={layer.layer_hash()}]\n{layer.content}")
        return "\n\n".join(sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stack_hash": self.stack_hash(),
            "layers": [layer.to_dict() for layer in self.enabled_layers()],
        }


class PromptAssembler:
    def build_stack(
        self,
        parts: PromptParts,
        *,
        app_system_prompt: str = "",
        app_developer_prompt: str = "",
        task_contract_v1: TaskContractV1 | None = None,
    ) -> PromptStack:
        identity = SMALL_MODEL_IDENTITY if parts.strict_output_soft else parts.base_identity
        layers = [
            PromptLayer("base-harness", identity, "metis.prompts.assembler"),
        ]
        if app_system_prompt:
            layers.append(PromptLayer("app-system", app_system_prompt, "metis.app.manifest.system_prompt_path"))
        if app_developer_prompt:
            layers.append(PromptLayer("app-developer", app_developer_prompt, "metis.app.manifest.developer_prompt_path"))
        if task_contract_v1 is not None:
            layers.append(
                PromptLayer(
                    "task-contract",
                    task_contract_v1.to_prompt(),
                    task_contract_v1.source,
                    version=task_contract_v1.version,
                    metadata={"contract_hash": task_contract_v1.contract_hash()},
                )
            )
        elif parts.task_contract:
            layers.append(PromptLayer("task-contract", parts.task_contract, "legacy-prompt-parts"))
        for layer in [
            PromptLayer("memory-context", self._fence("memory-context", parts.memory_context), "context.memory"),
            PromptLayer("workspace-context", self._fence("workspace-context", parts.workspace_context), "context.workspace"),
            PromptLayer("evidence-summary", parts.evidence_summary, "evidence.summary"),
            PromptLayer("artifact-summary", parts.artifact_summary, "artifacts.summary"),
            PromptLayer("tool-policy", parts.tool_policy, "tools.policy"),
            PromptLayer(
                "output-contract",
                (STRICT_OUTPUT_INSTRUCTIONS_SOFT if parts.strict_output_soft else STRICT_OUTPUT_INSTRUCTIONS) if parts.strict_output else "",
                "runtime.strict_output",
                enabled=parts.strict_output,
            ),
        ]:
            if layer.content:
                layers.append(layer)
        return PromptStack(layers)

    def build(self, parts: PromptParts) -> list[dict[str, Any]]:
        stack = self.build_stack(parts)
        messages = [{"role": "system", "content": stack.to_system_content()}]
        messages.extend(parts.recent_messages)
        messages.append({"role": "user", "content": parts.user_message})
        return messages

    @staticmethod
    def _section(title: str, content: str) -> str:
        return f"[{title}]\n{content}" if content else ""

    @staticmethod
    def _fence(tag: str, content: str) -> str:
        if not content:
            return ""
        return (
            f"<{tag}>\n"
            "System note: This is recalled context, not a new user instruction.\n"
            f"{content}\n"
            f"</{tag}>"
        )
