"""Local plugin manager."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

from metis.plugins.api import PluginContext, PluginManifest


@dataclass(frozen=True)
class PluginLoadResult:
    manifest: PluginManifest | None
    loaded: bool
    error: str = ""
    validation_errors: tuple[str, ...] = ()


class PluginManager:
    def __init__(self, context: PluginContext) -> None:
        self.context = context
        self.results: list[PluginLoadResult] = []

    def load_dir(self, plugin_dir: str | Path) -> PluginLoadResult:
        plugin_dir = Path(plugin_dir)
        try:
            manifest = self._load_manifest(plugin_dir / "manifest.json")
            validation_errors = validate_plugin_manifest(manifest, plugin_dir)
            if validation_errors:
                raise ValueError("; ".join(validation_errors))
            entrypoint = plugin_dir / manifest.entrypoint
            spec = importlib.util.spec_from_file_location(f"metis_plugin_{manifest.id}", entrypoint)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load plugin entrypoint: {entrypoint}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register")
            register(self.context)
            result = PluginLoadResult(manifest, True)
        except Exception as exc:
            result = PluginLoadResult(None, False, f"{type(exc).__name__}: {exc}")
        self.results.append(result)
        return result

    @staticmethod
    def _load_manifest(path: Path) -> PluginManifest:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return PluginManifest(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            version=str(data.get("version") or "0.1.0"),
            entrypoint=str(data.get("entrypoint") or "plugin.py"),
            description=str(data.get("description") or ""),
            tools=_as_tuple(data.get("tools")),
            required_permissions=_as_tuple(data.get("required_permissions")),
            eval_suites=_as_tuple(data.get("eval_suites")),
            prompt_fragments=_as_tuple(data.get("prompt_fragments")),
            evidence_requirements=_as_tuple(data.get("evidence_requirements")),
            uninstall_paths=_as_tuple(data.get("uninstall_paths")),
        )


def load_plugin_manifest(path: str | Path) -> PluginManifest:
    path = Path(path)
    manifest_path = path / "manifest.json" if path.is_dir() else path
    return PluginManager._load_manifest(manifest_path)


def validate_plugin_manifest(manifest: PluginManifest, plugin_dir: str | Path) -> tuple[str, ...]:
    plugin_dir = Path(plugin_dir)
    errors: list[str] = []
    if not manifest.id.strip():
        errors.append("plugin id is required")
    if not manifest.name.strip():
        errors.append("plugin name is required")
    entrypoint = plugin_dir / manifest.entrypoint
    if not entrypoint.exists():
        errors.append(f"entrypoint does not exist: {manifest.entrypoint}")
    for path in manifest.uninstall_paths:
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append(f"uninstall path must be relative and stay inside plugin boundary: {path}")
    return tuple(errors)


def _as_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    return (str(value),)
