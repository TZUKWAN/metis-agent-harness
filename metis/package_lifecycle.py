"""Build and verify portable Metis downstream agent packages."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


PACKAGE_MANIFEST = "metis-package.json"


def build_package(source_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    source = Path(source_dir)
    output = Path(output_dir)
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"Package source directory does not exist: {source}")
    if output.resolve() != source.resolve():
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(source, output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = _package_manifest(output)
    (output / PACKAGE_MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def verify_package(package_dir: str | Path, *, profile: str = "dev") -> dict[str, Any]:
    root = Path(package_dir)
    failures: list[str] = []
    warnings: list[str] = []
    manifest_path = root / "metis-agent.json"
    package_manifest_path = root / PACKAGE_MANIFEST
    manifest: dict[str, Any] = {}
    if not root.exists() or not root.is_dir():
        failures.append(f"Package directory does not exist: {root}")
        return _verification(root, profile, failures, warnings)
    if not manifest_path.exists():
        failures.append("metis-agent.json missing")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        for key in ["name", "workspace", "model", "profile"]:
            if not manifest.get(key):
                failures.append(f"metis-agent.json missing required field: {key}")
        for key in ["system_prompt_path", "developer_prompt_path"]:
            prompt_path = str(manifest.get(key, ""))
            if prompt_path and not (root / prompt_path).exists():
                failures.append(f"Prompt path from {key} does not exist: {prompt_path}")
    if not (root / "README.md").exists():
        failures.append("README.md missing")
    if not package_manifest_path.exists():
        warnings.append("metis-package.json missing; run metis package build to record file hashes")
    else:
        failures.extend(_verify_file_hashes(root, json.loads(package_manifest_path.read_text(encoding="utf-8-sig"))))
    eval_suites = list((root / "evals").glob("*.json")) if (root / "evals").exists() else []
    if profile in {"candidate", "release"} and not eval_suites:
        failures.append(f"{profile} package verification requires at least one eval suite under evals/")
    slash_command_count = len(list((root / ".claude" / "commands").glob("*.md"))) + len(
        list((root / ".codex" / "commands").glob("*.md"))
    )
    if slash_command_count == 0:
        warnings.append("No Claude Code or Codex slash commands found")
    return _verification(root, profile, failures, warnings, manifest=manifest, eval_suite_count=len(eval_suites))


def install_package(package_dir: str | Path, install_dir: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    source = Path(package_dir)
    target = Path(install_dir)
    verification = verify_package(source, profile="dev")
    if not verification["valid"]:
        raise ValueError("Package verification failed before install: " + "; ".join(verification["failures"]))
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"Install directory already exists: {target}")
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return {"installed": True, "source": str(source), "install_dir": str(target)}


def export_package(package_dir: str | Path, output_zip: str | Path) -> dict[str, Any]:
    source = Path(package_dir)
    verification = verify_package(source, profile="dev")
    if not verification["valid"]:
        raise ValueError("Package verification failed before export: " + "; ".join(verification["failures"]))
    output = Path(output_zip)
    output.parent.mkdir(parents=True, exist_ok=True)
    archive_base = output.with_suffix("")
    created = shutil.make_archive(str(archive_base), "zip", root_dir=source)
    created_path = Path(created)
    if created_path != output:
        if output.exists():
            output.unlink()
        created_path.replace(output)
    return {"exported": True, "package_dir": str(source), "archive": str(output), "sha256": _sha256(output)}


def _package_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != PACKAGE_MANIFEST):
        rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "sha256": _sha256(path), "size": path.stat().st_size})
    return {
        "artifact_type": "metis_agent_package",
        "schema_version": "package-v1",
        "root": str(root),
        "file_count": len(files),
        "files": files,
    }


def _verify_file_hashes(root: Path, manifest: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for item in manifest.get("files", []):
        path = root / str(item.get("path", ""))
        expected = str(item.get("sha256", ""))
        if not path.exists():
            failures.append(f"Package manifest file missing: {item.get('path', '')}")
            continue
        observed = _sha256(path)
        if observed != expected:
            failures.append(f"Package manifest hash mismatch: {item.get('path', '')}")
    return failures


def _verification(
    root: Path,
    profile: str,
    failures: list[str],
    warnings: list[str],
    *,
    manifest: dict[str, Any] | None = None,
    eval_suite_count: int = 0,
) -> dict[str, Any]:
    return {
        "package_dir": str(root),
        "profile": profile,
        "valid": not failures,
        "failures": failures,
        "warnings": warnings,
        "manifest": manifest or {},
        "eval_suite_count": eval_suite_count,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
