"""Small built-in tools for Sprint 1 tests and CLI smoke usage."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

from metis.security.paths import is_read_denied, is_write_denied, resolve_workspace_path
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolPermissionLevel, ToolSpec


def register_builtin_tools(registry: ToolRegistry, workspace: str = ".") -> None:
    root = Path(workspace).resolve()

    def _safe_path(raw: str) -> Path:
        return resolve_workspace_path(root, raw)

    def read_file(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_read_denied(path):
            raise PermissionError("Read denied by path security policy")
        encoding = args.get("encoding", "utf-8")
        return {"path": str(path), "content": path.read_text(encoding=encoding)}

    def write_file(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_write_denied(path):
            raise PermissionError("Write denied by path security policy")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(args.get("content", "")), encoding=args.get("encoding", "utf-8"))
        return {"path": str(path), "written": True}

    def run_shell(args: dict, context: ToolContext) -> dict:
        completed = subprocess.run(
            str(args["command"]),
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            timeout=int(args.get("timeout", 30)),
        )
        return {
            "command": str(args["command"]),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def _command_parts(raw: Any) -> list[str]:
        if isinstance(raw, list):
            return [str(item) for item in raw]
        return shlex.split(str(raw))

    def run_command(args: dict, context: ToolContext) -> dict:
        command = _command_parts(args["command"])
        completed = subprocess.run(
            command,
            cwd=root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=int(args.get("timeout", 30)),
        )
        return {
            "command": command,
            "command_text": " ".join(command),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def run_test(args: dict, context: ToolContext) -> dict:
        command = _command_parts(args.get("command", "python -m pytest -q"))
        completed = subprocess.run(
            command,
            cwd=root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=int(args.get("timeout", 60)),
        )
        return {
            "command": command,
            "command_text": " ".join(command),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "test_framework": "pytest" if "pytest" in " ".join(command).lower() else "unknown",
            "passed": completed.returncode == 0,
        }

    registry.register(
        ToolSpec(
            name="read_file",
            description="Read a UTF-8 text file inside the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "encoding": {"type": "string", "enum": ["utf-8", "utf-8-sig"]},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=read_file,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="write_file",
            description="Write a text file inside the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string"},
                    "encoding": {"type": "string", "enum": ["utf-8", "utf-8-sig"]},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            handler=write_file,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="run_shell",
            description="Run a shell command in the workspace.",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string", "minLength": 1}, "timeout": {"type": "integer", "minimum": 1, "maximum": 3600}},
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=run_shell,
            category="shell",
            side_effect="write",
            permission_level=ToolPermissionLevel.SHELL_DANGEROUS.value,
            metadata={"risk_level": "execute", "uses_shell": True},
        )
    )
    registry.register(
        ToolSpec(
            name="run_command",
            description="Run a command argument list in the workspace without a shell.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "oneOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
                        ]
                    },
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=run_command,
            category="shell",
            side_effect="write",
            permission_level=ToolPermissionLevel.SHELL_SAFE.value,
            metadata={"risk_level": "execute", "uses_shell": False},
        )
    )
    registry.register(
        ToolSpec(
            name="run_test",
            description="Run a test command in the workspace without a shell and return structured test metadata.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "oneOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
                        ]
                    },
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 3600},
                },
                "additionalProperties": False,
            },
            handler=run_test,
            category="test",
            side_effect="write",
            permission_level=ToolPermissionLevel.SHELL_SAFE.value,
            metadata={"risk_level": "execute", "uses_shell": False, "evidence_type": "test"},
        )
    )
