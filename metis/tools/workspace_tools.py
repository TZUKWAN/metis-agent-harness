"""Workspace navigation and file management tools."""

from __future__ import annotations

import os
from pathlib import Path

from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolPermissionLevel, ToolSpec


def register_workspace_tools(registry: ToolRegistry, *, workspace: str = ".") -> None:
    root = Path(workspace).resolve()

    def list_dir(args: dict, context: ToolContext) -> dict:
        """List files and directories at the given path."""
        rel_path = args.get("path", ".")
        full_path = (root / rel_path).resolve()
        if not str(full_path).startswith(str(root)):
            return {"error": "Path outside workspace", "entries": []}
        if not full_path.exists():
            return {"error": f"Path not found: {rel_path}", "entries": []}

        entries = []
        for item in sorted(full_path.iterdir()):
            entry = {"name": item.name, "type": "dir" if item.is_dir() else "file"}
            if item.is_file():
                try:
                    entry["size"] = item.stat().st_size
                except OSError:
                    pass
            entries.append(entry)
        return {"path": rel_path, "entries": entries}

    def search_files(args: dict, context: ToolContext) -> dict:
        """Search for files matching a pattern recursively."""
        import fnmatch

        pattern = args.get("pattern", "*")
        rel_path = args.get("path", ".")
        full_path = (root / rel_path).resolve()
        if not str(full_path).startswith(str(root)):
            return {"error": "Path outside workspace", "files": []}
        if not full_path.exists():
            return {"error": f"Path not found: {rel_path}", "files": []}

        matches = []
        for dirpath, _dirnames, filenames in os.walk(full_path):
            for filename in filenames:
                if fnmatch.fnmatch(filename, pattern):
                    abs_file = Path(dirpath) / filename
                    try:
                        rel = abs_file.relative_to(root)
                    except ValueError:
                        continue
                    matches.append({"path": str(rel).replace("\\", "/"), "size": abs_file.stat().st_size})
        return {"pattern": pattern, "files": matches}

    def append_to_file(args: dict, context: ToolContext) -> dict:
        """Append content to an existing file, or create it if it does not exist."""
        path = args["path"]
        content = args["content"]
        full_path = (root / path).resolve()
        if not str(full_path).startswith(str(root)):
            return {"error": "Path outside workspace"}
        from metis.security.paths import is_write_denied
        if is_write_denied(str(full_path)):
            return {"error": f"Write denied for security: {path}"}

        full_path.parent.mkdir(parents=True, exist_ok=True)
        existed = full_path.exists()
        with open(full_path, "a", encoding="utf-8") as f:
            f.write(content)
        return {"path": str(full_path), "appended": True, "created": not existed}

    def rename_file(args: dict, context: ToolContext) -> dict:
        old_path = args["old_path"]
        new_path = args["new_path"]
        old_full = (root / old_path).resolve()
        new_full = (root / new_path).resolve()
        if not str(old_full).startswith(str(root)) or not str(new_full).startswith(str(root)):
            return {"error": "Path outside workspace"}
        from metis.security.paths import is_write_denied
        if is_write_denied(str(old_full)) or is_write_denied(str(new_full)):
            return {"error": "Write denied for security"}
        if not old_full.exists():
            return {"error": f"Source not found: {old_path}"}
        new_full.parent.mkdir(parents=True, exist_ok=True)
        old_full.rename(new_full)
        return {"old_path": str(old_full), "new_path": str(new_full), "renamed": True}

    def delete_file(args: dict, context: ToolContext) -> dict:
        path = args["path"]
        full_path = (root / path).resolve()
        if not str(full_path).startswith(str(root)):
            return {"error": "Path outside workspace"}
        from metis.security.paths import is_write_denied
        if is_write_denied(str(full_path)):
            return {"error": f"Write denied for security: {path}"}
        if not full_path.exists():
            return {"error": f"File not found: {path}"}
        if full_path.is_dir():
            return {"error": "Cannot delete directories, only files"}
        full_path.unlink()
        return {"path": str(full_path), "deleted": True}

    def mkdir(args: dict, context: ToolContext) -> dict:
        path = args["path"]
        full_path = (root / path).resolve()
        if not str(full_path).startswith(str(root)):
            return {"error": "Path outside workspace"}
        from metis.security.paths import is_write_denied
        if is_write_denied(str(full_path)):
            return {"error": f"Write denied for security: {path}"}
        existed = full_path.exists()
        full_path.mkdir(parents=True, exist_ok=True)
        return {"path": str(full_path), "created": not existed}

    def copy_file(args: dict, context: ToolContext) -> dict:
        import shutil
        src_path = args["source"]
        dst_path = args["destination"]
        src_full = (root / src_path).resolve()
        dst_full = (root / dst_path).resolve()
        if not str(src_full).startswith(str(root)) or not str(dst_full).startswith(str(root)):
            return {"error": "Path outside workspace"}
        from metis.security.paths import is_read_denied, is_write_denied
        if is_read_denied(str(src_full)):
            return {"error": f"Read denied for security: {src_path}"}
        if is_write_denied(str(dst_full)):
            return {"error": f"Write denied for security: {dst_path}"}
        if not src_full.exists():
            return {"error": f"Source not found: {src_path}"}
        dst_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_full, dst_full)
        return {"source": str(src_full), "destination": str(dst_full), "copied": True, "size": dst_full.stat().st_size}

    registry.register(
        ToolSpec(
            name="list_dir",
            description="List files and directories in a path. Returns names, types (file/dir), and sizes. Use '.' for workspace root.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "additionalProperties": False,
            },
            handler=list_dir,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="search_files",
            description="Search for files by name pattern (e.g. '*.py', 'test_*'). Returns matching file paths and sizes.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            handler=search_files,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="append_to_file",
            description="Append text to a file. Creates the file if it does not exist. Does not overwrite existing content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            handler=append_to_file,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="rename_file",
            description="Rename or move a file. The old path must exist, the new path must not.",
            parameters={
                "type": "object",
                "properties": {
                    "old_path": {"type": "string", "minLength": 1},
                    "new_path": {"type": "string", "minLength": 1},
                },
                "required": ["old_path", "new_path"],
                "additionalProperties": False,
            },
            handler=rename_file,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="delete_file",
            description="Delete a single file. Cannot delete directories.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=delete_file,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="copy_file",
            description="Copy a file to a new location. Preserves metadata. Creates destination directory if needed.",
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "minLength": 1},
                    "destination": {"type": "string", "minLength": 1},
                },
                "required": ["source", "destination"],
                "additionalProperties": False,
            },
            handler=copy_file,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="mkdir",
            description="Create a directory and any missing parent directories. Safe if directory already exists.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=mkdir,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
