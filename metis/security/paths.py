"""Workspace path security checks."""

from __future__ import annotations

from pathlib import Path

DENY_PARTS = {".ssh", ".aws", ".gnupg", ".kube", ".docker"}
DENY_FILES = {".env", ".netrc", ".bashrc", ".zshrc", ".profile", "powershell_profile.ps1"}
SYSTEM_ROOT_HINTS = ("windows", "program files", "programdata")


def resolve_workspace_path(workspace: str | Path, raw_path: str | Path) -> Path:
    root = Path(workspace).resolve()
    path = (root / raw_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise PermissionError("Path escapes workspace") from exc
    return path


def is_read_denied(path: str | Path) -> bool:
    return _is_denied(path)


def is_write_denied(path: str | Path) -> bool:
    return _is_denied(path)


def _is_denied(path: str | Path) -> bool:
    resolved = Path(path).resolve()
    parts = {part.lower() for part in resolved.parts}
    if any(part in parts for part in DENY_PARTS):
        return True
    if resolved.name.lower() in DENY_FILES:
        return True
    lowered = str(resolved).lower()
    return any(hint in lowered for hint in SYSTEM_ROOT_HINTS)
