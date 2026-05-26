"""Built-in tools with safe command execution."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from metis.config import MAX_CONTENT_LENGTH, MAX_TIMEOUT
from metis.security.paths import is_read_denied, is_write_denied, resolve_workspace_path
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolPermissionLevel, ToolSpec

_ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_PATTERN.sub("", text)


ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "grep", "find", "wc", "echo", "sort", "uniq",
    "python", "python3", "pip", "pytest", "coverage",
    "git", "npm", "npx", "yarn", "pnpm",
    "curl", "wget",
    "mkdir", "cp", "mv", "touch", "chmod",
    "node", "tsc", "eslint",
    "go", "cargo", "rustc",
    "java", "mvn", "gradle",
    "docker", "podman",
}


DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/(\s|$)", re.IGNORECASE),
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?~(\s|$)", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bdel\s+/[a-zA-Z]*s[a-zA-Z]*\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bdd\s+if=.*of=/dev/", re.IGNORECASE),
    re.compile(r">\s*/dev/sd", re.IGNORECASE),
    re.compile(r"\bchmod\s+(-[a-zA-Z]*\s+)?000\s+", re.IGNORECASE),
    re.compile(r"\bmv\s+.*\s+/dev/null", re.IGNORECASE),
    re.compile(r"\bgit\s+push\s+.*--force", re.IGNORECASE),
    re.compile(r"\bgit\s+reset\s+--hard", re.IGNORECASE),
    re.compile(r"\bgit\s+clean\s+-[a-zA-Z]*f", re.IGNORECASE),
    re.compile(r"\bgit\s+checkout\s+\.", re.IGNORECASE),
]


def _validate_command(command_parts: list[str]) -> str | None:
    if not command_parts:
        return "Empty command"
    base = Path(command_parts[0]).name.lower()
    if base not in ALLOWED_COMMANDS:
        return f"Command not in allowlist: {base}"
    return None


def _check_dangerous_patterns(command_str: str) -> str | None:
    for pattern in DANGEROUS_PATTERNS:
        match = pattern.search(command_str)
        if match:
            return f"Blocked dangerous command pattern: {match.group()}"
    return None


def register_builtin_tools(registry: ToolRegistry, workspace: str = ".", *, allowed_commands: set[str] | None = None) -> None:
    root = Path(workspace).resolve()
    effective_allowed = (ALLOWED_COMMANDS | (allowed_commands or set())) if allowed_commands else ALLOWED_COMMANDS

    def _safe_path(raw: str) -> Path:
        return resolve_workspace_path(root, raw)

    def read_file(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_read_denied(path):
            raise PermissionError("Read denied by path security policy")
        encoding = str(args.get("encoding", "auto"))
        if encoding == "auto":
            for enc in ("utf-8", "utf-8-sig", "latin-1"):
                try:
                    content = path.read_text(encoding=enc)
                    return {"path": str(path), "content": content, "encoding": enc}
                except (UnicodeDecodeError, UnicodeError):
                    continue
            return {"path": str(path), "error": "Could not decode file with any supported encoding"}
        return {"path": str(path), "content": path.read_text(encoding=encoding), "encoding": encoding}

    def write_file(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_write_denied(path):
            raise PermissionError("Write denied by path security policy")
        content = str(args.get("content", ""))
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Content exceeds maximum length ({MAX_CONTENT_LENGTH} chars)")
        path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = None
        if path.exists() and path.is_file():
            backup_path = path.with_suffix(path.suffix + ".bak")
            try:
                backup_path.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            except OSError:
                backup_path = None
        path.write_text(content, encoding=args.get("encoding", "utf-8"))
        result: dict[str, Any] = {"path": str(path), "written": True}
        if backup_path is not None:
            result["backup"] = str(backup_path)
        return result

    def edit_file(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_write_denied(path):
            raise PermissionError("Write denied by path security policy")
        if not path.exists():
            return {"path": str(path), "error": "File not found"}
        old_text = str(args["old_text"])
        new_text = str(args["new_text"])
        content = path.read_text(encoding="utf-8")
        if old_text not in content:
            return {"path": str(path), "error": "old_text not found in file", "matched": False}
        if content.count(old_text) > 1:
            return {"path": str(path), "error": f"old_text matches {content.count(old_text)} times, must be unique", "matched": False}
        updated = content.replace(old_text, new_text, 1)
        path.write_text(updated, encoding="utf-8")
        return {"path": str(path), "edited": True, "matched": True}

    def append_file(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_write_denied(path):
            raise PermissionError("Write denied by path security policy")
        content = str(args.get("content", ""))
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Content exceeds maximum length ({MAX_CONTENT_LENGTH} chars)")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return {"path": str(path), "appended": True, "content_length": len(content)}

    def diff_files(args: dict, context: ToolContext) -> dict:
        path_a = _safe_path(str(args["path_a"]))
        path_b = _safe_path(str(args["path_b"]))
        if is_read_denied(path_a) or is_read_denied(path_b):
            raise PermissionError("Read denied by path security policy")
        if not path_a.is_file():
            return {"error": f"File not found: {path_a}"}
        if not path_b.is_file():
            return {"error": f"File not found: {path_b}"}
        try:
            lines_a = path_a.read_text(encoding="utf-8", errors="ignore").splitlines()
            lines_b = path_b.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            return {"error": str(exc)}
        max_diff_lines = min(int(args.get("max_diff_lines", 200)), 1000)
        diffs: list[dict[str, Any]] = []
        from itertools import zip_longest
        for i, (la, lb) in enumerate(zip_longest(lines_a, lines_b, fillvalue=None)):
            if la != lb:
                entry: dict[str, Any] = {"line": i + 1}
                if la is not None:
                    entry["a"] = la
                if lb is not None:
                    entry["b"] = lb
                diffs.append(entry)
                if len(diffs) >= max_diff_lines:
                    break
        return {
            "path_a": str(path_a),
            "path_b": str(path_b),
            "lines_a": len(lines_a),
            "lines_b": len(lines_b),
            "differences": diffs,
            "diff_count": len(diffs),
            "truncated": len(diffs) >= max_diff_lines,
        }

    def get_environment(args: dict, context: ToolContext) -> dict:
        workspace_path = _safe_path(str(args.get("path", ".")))
        env_info: dict[str, Any] = {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "python_executable": sys.executable,
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "cwd": str(workspace_path),
        }
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                env_info["packages_count"] = len(packages)
                env_info["packages"] = [
                    {"name": p["name"], "version": p["version"]}
                    for p in packages[:50]
                ]
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            env_info["packages_count"] = 0
        if workspace_path.is_dir():
            top_entries = []
            for item in sorted(workspace_path.iterdir(), key=lambda p: p.name.lower()):
                if item.name.startswith("."):
                    continue
                top_entries.append(item.name)
                if len(top_entries) >= 30:
                    break
            env_info["workspace_top_entries"] = top_entries
        return env_info

    def compute_hash(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if not path.is_file():
            return {"path": str(path), "error": "Not a file or not found"}
        if is_read_denied(path):
            raise PermissionError("Read denied by path security policy")
        algorithm = str(args.get("algorithm", "sha256")).lower()
        if algorithm not in {"sha256", "sha1", "md5"}:
            return {"path": str(path), "error": f"Unsupported algorithm: {algorithm}. Use sha256, sha1, or md5."}
        h = hashlib.new(algorithm)
        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
        except OSError as exc:
            return {"path": str(path), "error": str(exc)}
        return {"path": str(path), "algorithm": algorithm, "hash": h.hexdigest(), "file_size": path.stat().st_size}

    def path_exists(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        return {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "is_dir": path.is_dir() if path.exists() else False,
        }

    def read_files(args: dict, context: ToolContext) -> dict:
        paths_raw = args.get("paths", [])
        if not isinstance(paths_raw, list) or not paths_raw:
            return {"error": "paths must be a non-empty array", "results": {}}
        if len(paths_raw) > 20:
            return {"error": f"Too many paths: {len(paths_raw)}, max 20", "results": {}}
        results: dict[str, Any] = {}
        for raw_path in paths_raw:
            path = _safe_path(str(raw_path))
            if is_read_denied(path):
                results[str(raw_path)] = {"error": "Read denied by path security policy"}
                continue
            if not path.is_file():
                results[str(raw_path)] = {"error": "Not a file or not found"}
                continue
            try:
                results[str(raw_path)] = {"content": path.read_text(encoding="utf-8", errors="ignore"), "size": path.stat().st_size}
            except OSError as exc:
                results[str(raw_path)] = {"error": str(exc)}
        return {"results": results, "count": len(results)}

    def detect_file_type(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if not path.is_file():
            return {"path": str(path), "error": "Not a file or not found"}
        if is_read_denied(path):
            raise PermissionError("Read denied by path security policy")
        ext_to_lang = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript (React)",
            ".jsx": "JavaScript (React)", ".go": "Go", ".rs": "Rust", ".java": "Java",
            ".cpp": "C++", ".c": "C", ".h": "C/C++ Header", ".hpp": "C++ Header",
            ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin",
            ".sh": "Shell", ".bash": "Bash", ".zsh": "Zsh",
            ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".less": "LESS",
            ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
            ".xml": "XML", ".md": "Markdown", ".rst": "reStructuredText",
            ".sql": "SQL", ".graphql": "GraphQL", ".tf": "Terraform",
            ".txt": "Plain Text", ".csv": "CSV", ".log": "Log",
        }
        ext = path.suffix.lower()
        name_lower = path.name.lower()
        language = ext_to_lang.get(ext, "Unknown")
        if language == "Unknown":
            if name_lower == "dockerfile":
                language = "Dockerfile"
            elif name_lower == "makefile":
                language = "Makefile"
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
        except OSError:
            lines = []
        return {
            "path": str(path),
            "extension": ext,
            "language": language,
            "size": path.stat().st_size,
            "total_lines": len(lines),
            "non_empty_lines": sum(1 for line in lines if line.strip()),
            "blank_lines": sum(1 for line in lines if not line.strip()),
        }

    _memory_store: dict[str, str] = {}

    def store_memory(args: dict, context: ToolContext) -> dict:
        key = str(args["key"])
        value = str(args["value"])
        if len(key) > 200:
            return {"error": "Key too long (max 200 chars)"}
        if len(value) > 10000:
            return {"error": "Value too long (max 10000 chars)"}
        _memory_store[key] = value
        return {"stored": True, "key": key}

    def recall_memory(args: dict, context: ToolContext) -> dict:
        key = str(args.get("key", ""))
        if key:
            value = _memory_store.get(key)
            if value is None:
                return {"key": key, "found": False}
            return {"key": key, "value": value, "found": True}
        return {"keys": list(_memory_store.keys()), "count": len(_memory_store)}

    def rename_file(args: dict, context: ToolContext) -> dict:
        old_path = _safe_path(str(args["old_path"]))
        new_path = _safe_path(str(args["new_path"]))
        if is_write_denied(old_path) or is_write_denied(new_path):
            raise PermissionError("Write denied by path security policy")
        if not old_path.exists():
            return {"old_path": str(old_path), "error": "Source not found"}
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
        return {"old_path": str(old_path), "new_path": str(new_path), "renamed": True}

    def delete_file(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_write_denied(path):
            raise PermissionError("Write denied by path security policy")
        if not path.exists():
            return {"path": str(path), "error": "Not found"}
        if path.is_dir():
            return {"path": str(path), "error": "Cannot delete directories, only files"}
        path.unlink()
        return {"path": str(path), "deleted": True}

    def copy_file(args: dict, context: ToolContext) -> dict:
        import shutil
        src = _safe_path(str(args["source"]))
        dst = _safe_path(str(args["destination"]))
        if is_read_denied(src):
            raise PermissionError("Read denied by path security policy")
        if is_write_denied(dst):
            raise PermissionError("Write denied by path security policy")
        if not src.exists():
            return {"source": str(src), "error": "Source not found"}
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return {"source": str(src), "destination": str(dst), "copied": True, "size": dst.stat().st_size}

    def mkdir(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if is_write_denied(path):
            raise PermissionError("Write denied by path security policy")
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        return {"path": str(path), "created": not existed}

    def run_shell(args: dict, context: ToolContext) -> dict:
        command_str = str(args["command"])
        timeout = min(int(args.get("timeout", 30)), MAX_TIMEOUT)
        danger = _check_dangerous_patterns(command_str)
        if danger:
            return {"command": command_str, "exit_code": -1, "stdout": "", "stderr": danger}
        try:
            parts = shlex.split(command_str)
        except ValueError:
            parts = command_str.split()
        error = _validate_command(parts)
        if error:
            if effective_allowed is ALLOWED_COMMANDS:
                base = Path(parts[0]).name.lower() if parts else ""
                if base not in effective_allowed:
                    return {
                        "command": command_str,
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": f"Blocked: {error}. Use run_command for non-shell execution.",
                    }
        completed = subprocess.run(
            parts,
            cwd=root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command_str,
            "exit_code": completed.returncode,
            "stdout": _strip_ansi(completed.stdout),
            "stderr": _strip_ansi(completed.stderr),
        }

    def _command_parts(raw: Any) -> list[str]:
        if isinstance(raw, list):
            return [str(item) for item in raw]
        return shlex.split(str(raw))

    def run_command(args: dict, context: ToolContext) -> dict:
        command = _command_parts(args["command"])
        timeout = min(int(args.get("timeout", 30)), MAX_TIMEOUT)
        command_text = " ".join(command)
        danger = _check_dangerous_patterns(command_text)
        if danger:
            return {"command": command, "command_text": command_text, "exit_code": -1, "stdout": "", "stderr": danger}
        error = _validate_command(command)
        if error:
            base = Path(command[0]).name.lower() if command else ""
            if base not in effective_allowed:
                return {
                    "command": command,
                    "command_text": " ".join(command),
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Blocked: {error}",
                }
        completed = subprocess.run(
            command,
            cwd=root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "command_text": " ".join(command),
            "exit_code": completed.returncode,
            "stdout": _strip_ansi(completed.stdout),
            "stderr": _strip_ansi(completed.stderr),
        }

    def run_test(args: dict, context: ToolContext) -> dict:
        command = _command_parts(args.get("command", "python -m pytest -q"))
        timeout = min(int(args.get("timeout", 60)), MAX_TIMEOUT)
        completed = subprocess.run(
            command,
            cwd=root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "command": command,
            "command_text": " ".join(command),
            "exit_code": completed.returncode,
            "stdout": _strip_ansi(completed.stdout),
            "stderr": _strip_ansi(completed.stderr),
            "test_framework": "pytest" if "pytest" in " ".join(command).lower() else "unknown",
            "passed": completed.returncode == 0,
        }

    def get_file_info(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if not path.exists():
            return {"path": str(path), "error": "File not found"}
        if is_read_denied(path):
            raise PermissionError("Read denied by path security policy")
        stat = path.stat()
        return {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix,
            "size": stat.st_size,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "modified": stat.st_mtime,
        }

    def count_lines(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if not path.is_file():
            return {"path": str(path), "error": "Not a file or not found"}
        if is_read_denied(path):
            raise PermissionError("Read denied by path security policy")
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            return {"path": str(path), "error": str(exc)}
        non_empty = sum(1 for line in lines if line.strip())
        return {"path": str(path), "total_lines": len(lines), "non_empty_lines": non_empty, "blank_lines": len(lines) - non_empty}

    def read_file_range(args: dict, context: ToolContext) -> dict:
        path = _safe_path(str(args["path"]))
        if not path.is_file():
            return {"path": str(path), "error": "Not a file or not found"}
        if is_read_denied(path):
            raise PermissionError("Read denied by path security policy")
        offset = max(int(args.get("offset", 0)), 0)
        limit = min(int(args.get("limit", 100)), 2000)
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            return {"path": str(path), "error": str(exc)}
        selected = lines[offset: offset + limit]
        numbered = {str(i + offset + 1): line for i, line in enumerate(selected)}
        return {
            "path": str(path),
            "offset": offset,
            "limit": limit,
            "total_lines": len(lines),
            "lines_returned": len(selected),
            "content": "\n".join(selected),
            "numbered": numbered,
        }

    def search_code(args: dict, context: ToolContext) -> dict:
        pattern = str(args["pattern"])
        search_path = _safe_path(str(args.get("path", ".")))
        output_mode = str(args.get("output_mode", "files_with_matches"))
        case_insensitive = bool(args.get("case_insensitive", False))
        max_results = min(int(args.get("max_results", 100)), 500)

        if is_read_denied(search_path):
            raise PermissionError("Read denied by path security policy")

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return {"pattern": pattern, "error": f"Invalid regex: {exc}", "matches": []}

        matches: list[dict[str, Any]] = []
        for filepath in search_path.rglob("*"):
            if not filepath.is_file():
                continue
            if any(part.startswith(".") for part in filepath.relative_to(search_path).parts):
                continue
            if filepath.stat().st_size > 1_000_000:
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    if output_mode == "content":
                        matches.append({
                            "file": str(filepath.relative_to(root)),
                            "line": line_no,
                            "text": line[:200],
                        })
                    else:
                        matches.append({"file": str(filepath.relative_to(root))})
                        break
                if len(matches) >= max_results:
                    break
            if len(matches) >= max_results:
                break

        return {"pattern": pattern, "matches": matches, "count": len(matches)}

    def find_files(args: dict, context: ToolContext) -> dict:
        glob_pattern = str(args["pattern"])
        search_path = _safe_path(str(args.get("path", ".")))
        max_results = min(int(args.get("max_results", 200)), 1000)

        if is_read_denied(search_path):
            raise PermissionError("Read denied by path security policy")

        files: list[dict[str, Any]] = []
        for filepath in search_path.rglob(glob_pattern):
            if filepath.is_file():
                rel = filepath.relative_to(root)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                files.append({
                    "path": str(rel),
                    "name": filepath.name,
                    "size": filepath.stat().st_size,
                    "extension": filepath.suffix,
                })
                if len(files) >= max_results:
                    break

        return {"pattern": glob_pattern, "files": files, "count": len(files)}

    def list_directory(args: dict, context: ToolContext) -> dict:
        dir_path = _safe_path(str(args.get("path", ".")))
        max_entries = min(int(args.get("max_entries", 200)), 1000)
        show_hidden = bool(args.get("show_hidden", False))

        if is_read_denied(dir_path):
            raise PermissionError("Read denied by path security policy")
        if not dir_path.is_dir():
            return {"path": str(dir_path), "error": "Not a directory or not found"}

        entries: list[dict[str, Any]] = []
        try:
            items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return {"path": str(dir_path), "error": "Permission denied"}

        for item in items:
            name = item.name
            if not show_hidden and name.startswith("."):
                continue
            try:
                stat = item.stat()
            except OSError:
                continue
            entries.append({
                "name": name,
                "type": "directory" if item.is_dir() else "file",
                "size": stat.st_size if item.is_file() else 0,
                "extension": item.suffix if item.is_file() else "",
            })
            if len(entries) >= max_entries:
                break

        return {"path": str(dir_path), "entries": entries, "count": len(entries)}

    def tree_summary(args: dict, context: ToolContext) -> dict:
        dir_path = _safe_path(str(args.get("path", ".")))
        max_depth = min(int(args.get("max_depth", 3)), 6)
        max_entries = min(int(args.get("max_entries", 200)), 500)

        if is_read_denied(dir_path):
            raise PermissionError("Read denied by path security policy")
        if not dir_path.is_dir():
            return {"path": str(dir_path), "error": "Not a directory or not found"}

        lines: list[str] = []
        total_files = 0
        total_dirs = 0

        def _walk(current: Path, prefix: str, depth: int) -> None:
            nonlocal total_files, total_dirs
            if depth > max_depth:
                return
            try:
                items = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return
            for item in items:
                if item.name.startswith("."):
                    continue
                if len(lines) >= max_entries:
                    lines.append(f"{prefix}...")
                    return
                if item.is_dir():
                    total_dirs += 1
                    lines.append(f"{prefix}{item.name}/")
                    _walk(item, prefix + "  ", depth + 1)
                else:
                    total_files += 1
                    lines.append(f"{prefix}{item.name}")

        _walk(dir_path, "", 0)
        return {
            "path": str(dir_path),
            "tree": "\n".join(lines),
            "total_files": total_files,
            "total_dirs": total_dirs,
            "max_depth": max_depth,
        }

    registry.register(
        ToolSpec(
            name="read_file",
            description="Read the contents of a text file. Use this to inspect source code, config files, or any text file in the workspace.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "encoding": {"type": "string", "enum": ["auto", "utf-8", "utf-8-sig"]},
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
            description="Create or overwrite a text file with the given content. Use this to save generated code, reports, or any text output.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string", "maxLength": MAX_CONTENT_LENGTH},
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
            name="edit_file",
            description="Replace a unique text fragment in a file. Provide old_text (must appear exactly once) and new_text. Use this instead of write_file for small changes.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "old_text": {"type": "string", "minLength": 1},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
            handler=edit_file,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="append_file",
            description="Append content to the end of a file. Creates the file if it does not exist. Use for logs, incremental output, or adding to existing files.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "content": {"type": "string", "maxLength": MAX_CONTENT_LENGTH},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
            handler=append_file,
            category="files",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="diff_files",
            description="Compare two files line by line. Returns differences with line numbers. Useful for verifying changes.",
            parameters={
                "type": "object",
                "properties": {
                    "path_a": {"type": "string", "minLength": 1},
                    "path_b": {"type": "string", "minLength": 1},
                    "max_diff_lines": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
                "required": ["path_a", "path_b"],
                "additionalProperties": False,
            },
            handler=diff_files,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="get_environment",
            description="Get runtime environment info: Python version, platform, installed packages, and workspace structure. Helps understand the execution context.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "additionalProperties": False,
            },
            handler=get_environment,
            category="general",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="compute_hash",
            description="Compute hash of a file. Supports sha256, sha1, md5. Use for integrity verification.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "algorithm": {"type": "string", "enum": ["sha256", "sha1", "md5"]},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=compute_hash,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="path_exists",
            description="Check if a file or directory exists. Returns exists, is_file, is_dir. Faster than get_file_info for existence checks.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=path_exists,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="read_files",
            description="Read multiple files at once. Provide paths as an array. Returns content keyed by path. Max 20 files per call.",
            parameters={
                "type": "object",
                "properties": {
                    "paths": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "maxItems": 20},
                },
                "required": ["paths"],
                "additionalProperties": False,
            },
            handler=read_files,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="detect_file_type",
            description="Detect file type, programming language, and line statistics from extension and content.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=detect_file_type,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="store_memory",
            description="Store a key-value pair in session memory. Use to save intermediate results for later recall.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "minLength": 1, "maxLength": 200},
                    "value": {"type": "string", "maxLength": 10000},
                },
                "required": ["key", "value"],
                "additionalProperties": False,
            },
            handler=store_memory,
            category="general",
            side_effect="write",
            permission_level=ToolPermissionLevel.WORKSPACE_WRITE.value,
        )
    )
    registry.register(
        ToolSpec(
            name="recall_memory",
            description="Recall a value from session memory by key, or list all keys if no key given.",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                },
                "additionalProperties": False,
            },
            handler=recall_memory,
            category="general",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="rename_file",
            description="Rename or move a file. The source must exist. Creates parent directories for destination if needed.",
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
            description="Delete a single file. Cannot delete directories. Returns error if file does not exist.",
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
    registry.register(
        ToolSpec(
            name="run_shell",
            description="Execute a single command (no pipes, no redirections). Allowed: ls, cat, grep, python, git, npm, etc. Example: 'ls -la src/'",
            parameters={
                "type": "object",
                "properties": {"command": {"type": "string", "minLength": 1}, "timeout": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT}},
                "required": ["command"],
                "additionalProperties": False,
            },
            handler=run_shell,
            category="shell",
            side_effect="write",
            permission_level=ToolPermissionLevel.SHELL_DANGEROUS.value,
            timeout_seconds=120,
            metadata={"risk_level": "execute", "uses_shell": False},
        )
    )
    registry.register(
        ToolSpec(
            name="run_command",
            description="Execute a command with arguments as an array or string. Example: ['python', '-m', 'pytest', '-q']. No shell features.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "oneOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
                        ]
                    },
                    "timeout": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT},
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
            description="Run tests. Defaults to 'python -m pytest -q' if no command given. Returns pass/fail status and output.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "oneOf": [
                            {"type": "string", "minLength": 1},
                            {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1},
                        ]
                    },
                    "timeout": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT},
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
    registry.register(
        ToolSpec(
            name="get_file_info",
            description="Get file metadata: name, extension, size, type, modification time. Use to check if a file exists and its properties.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=get_file_info,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="count_lines",
            description="Count lines in a file. Returns total, non-empty, and blank line counts.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=count_lines,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="read_file_range",
            description="Read a range of lines from a file. Use offset (0-based) and limit to read parts of large files. Returns numbered lines.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 2000},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=read_file_range,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="search_code",
            description="Search for a regex pattern across files in the workspace. Returns matching files or matching lines with context.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                    "output_mode": {"type": "string", "enum": ["files_with_matches", "content"]},
                    "case_insensitive": {"type": "boolean"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            handler=search_code,
            category="search",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="find_files",
            description="Find files matching a glob pattern. Example: '**/*.py', 'src/**/*.ts', '*.json'. Returns file paths, sizes, and extensions.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "minLength": 1},
                    "path": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 1000},
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
            handler=find_files,
            category="search",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="list_directory",
            description="List directory contents. Returns entries with name, type (file/directory), size, and extension. Directories listed first.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_entries": {"type": "integer", "minimum": 1, "maximum": 1000},
                    "show_hidden": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            handler=list_directory,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
    registry.register(
        ToolSpec(
            name="tree_summary",
            description="Get a compact directory tree structure. Shows files and subdirectories up to max_depth with indentation. Directories end with '/'.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "max_depth": {"type": "integer", "minimum": 1, "maximum": 6},
                    "max_entries": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "additionalProperties": False,
            },
            handler=tree_summary,
            category="files",
            side_effect="read",
            permission_level=ToolPermissionLevel.READ_ONLY.value,
        )
    )
