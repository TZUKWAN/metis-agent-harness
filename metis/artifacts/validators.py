"""Artifact validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from metis.artifacts.store import ArtifactRecord, ArtifactStore

PLACEHOLDER_TERMS = ("TODO", "TBD", "placeholder", "mock", "dummy", "示例数据", "待补充")


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    message: str


def exists(artifact: ArtifactRecord) -> ValidationResult:
    path = Path(artifact.path)
    return ValidationResult(path.exists(), f"Artifact exists: {path}" if path.exists() else f"Missing artifact: {path}")


def non_empty(artifact: ArtifactRecord) -> ValidationResult:
    path = Path(artifact.path)
    passed = path.exists() and path.stat().st_size > 0
    return ValidationResult(passed, f"Artifact is non-empty: {path}" if passed else f"Artifact is empty or missing: {path}")


def extension_matches(artifact: ArtifactRecord, expected_extension: str) -> ValidationResult:
    expected = expected_extension if expected_extension.startswith(".") else f".{expected_extension}"
    passed = Path(artifact.path).suffix.lower() == expected.lower()
    return ValidationResult(passed, f"Extension matches {expected}" if passed else f"Extension does not match {expected}")


def no_placeholder(artifact: ArtifactRecord) -> ValidationResult:
    path = Path(artifact.path)
    if not path.exists():
        return ValidationResult(False, f"Missing artifact: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ValidationResult(True, "Binary artifact skipped for placeholder scan")
    lowered = text.lower()
    for term in PLACEHOLDER_TERMS:
        if term.lower() in lowered:
            return ValidationResult(False, f"Placeholder term found: {term}")
    return ValidationResult(True, "No placeholder terms found")


def checksum_matches(artifact: ArtifactRecord) -> ValidationResult:
    path = Path(artifact.path)
    if not path.exists():
        return ValidationResult(False, f"Missing artifact: {path}")
    actual = ArtifactStore.compute_checksum(path)
    passed = actual == artifact.checksum
    return ValidationResult(passed, "Checksum matches" if passed else "Checksum mismatch")
