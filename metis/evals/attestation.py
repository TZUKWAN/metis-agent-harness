"""Run artifact attestation helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_ATTESTATION_SCHEMA_VERSION = "1"
RUN_ATTESTATION_PREDICATE_TYPE = "https://metis.local/attestations/eval-run/v1"
REPAIR_PLAN_ATTESTATION_SCHEMA_VERSION = "1"
REPAIR_PLAN_ATTESTATION_PREDICATE_TYPE = "https://metis.local/attestations/repair-plan/v1"
REPAIR_EVAL_ARTIFACT_ATTESTATION_SCHEMA_VERSION = "1"
REPAIR_EVAL_ARTIFACT_ATTESTATION_PREDICATE_TYPE = "https://metis.local/attestations/repair-eval-artifacts/v1"
ATTESTATION_SIGNATURE_ALGORITHM = "hmac-sha256-v1"
ATTESTATION_SIGNING_KEY_ENV = "METIS_ATTESTATION_SIGNING_KEY"
ATTESTATION_KEY_ID_ENV = "METIS_ATTESTATION_KEY_ID"
ATTESTATION_REQUIRE_SIGNATURE_ENV = "METIS_REQUIRE_ATTESTATION_SIGNATURE"


def build_run_attestation(run_dir: str | Path, *, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    run_dir = Path(run_dir)
    manifest_payload = manifest or _load_json_if_exists(run_dir / "manifest.json")
    subjects = []
    for path in _attested_files(run_dir):
        subjects.append(_subject_for_path(run_dir, path))
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": RUN_ATTESTATION_PREDICATE_TYPE,
        "schema_version": RUN_ATTESTATION_SCHEMA_VERSION,
        "subject": subjects,
        "predicate": {
            "builder": {"id": "metis-agent-harness"},
            "run_dir": str(run_dir),
            "suite": manifest_payload.get("suite", ""),
            "run_name": manifest_payload.get("run_name", run_dir.name),
            "task_contract_hash": manifest_payload.get("task_contract_hash", ""),
            "provenance_hash": manifest_payload.get("provenance_hash", ""),
            "pre_run_contract_path": manifest_payload.get("pre_run_contract_path", ""),
            "pre_run_contract_sha256": manifest_payload.get("pre_run_contract_sha256", ""),
            "pre_run_provenance_hash": manifest_payload.get("pre_run_provenance_hash", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifact_count": len(subjects),
        },
    }


def write_run_attestation(run_dir: str | Path, *, manifest: dict[str, Any] | None = None) -> Path:
    run_dir = Path(run_dir)
    attestation = build_run_attestation(run_dir, manifest=manifest)
    _sign_attestation_if_configured(attestation)
    json_path = run_dir / "run-attestation.json"
    md_path = run_dir / "run-attestation.md"
    json_path.write_text(json.dumps(attestation, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(run_attestation_to_markdown(attestation), encoding="utf-8")
    return json_path


def build_repair_plan_attestation(output_dir: str | Path, *, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    output_dir = Path(output_dir)
    plan_payload = plan or _load_json_if_exists(output_dir / "repair-plan.json")
    subjects = []
    for path in _repair_plan_attested_files(output_dir):
        subjects.append(_subject_for_path(output_dir, path))
    phases = plan_payload.get("phases", []) if isinstance(plan_payload, dict) else []
    hard_preconditions = [
        str(phase.get("id", ""))
        for phase in phases
        if isinstance(phase, dict) and phase.get("hard_precondition")
    ]
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": REPAIR_PLAN_ATTESTATION_PREDICATE_TYPE,
        "schema_version": REPAIR_PLAN_ATTESTATION_SCHEMA_VERSION,
        "subject": subjects,
        "predicate": {
            "builder": {"id": "metis-agent-harness"},
            "output_dir": str(output_dir),
            "profile": plan_payload.get("profile", "") if isinstance(plan_payload, dict) else "",
            "task_count": plan_payload.get("task_count", 0) if isinstance(plan_payload, dict) else 0,
            "phase_count": len(phases) if isinstance(phases, list) else 0,
            "hard_preconditions": hard_preconditions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifact_count": len(subjects),
        },
    }


def write_repair_plan_attestation(output_dir: str | Path, *, plan: dict[str, Any] | None = None) -> Path:
    output_dir = Path(output_dir)
    attestation = build_repair_plan_attestation(output_dir, plan=plan)
    _sign_attestation_if_configured(attestation)
    json_path = output_dir / "repair-plan-attestation.json"
    md_path = output_dir / "repair-plan-attestation.md"
    json_path.write_text(json.dumps(attestation, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(repair_plan_attestation_to_markdown(attestation), encoding="utf-8")
    return json_path


def verify_repair_plan_attestation(output_dir: str | Path) -> list[str]:
    output_dir = Path(output_dir)
    attestation_path = output_dir / "repair-plan-attestation.json"
    if not attestation_path.exists():
        return ["repair-plan-attestation.json missing from repair plan directory"]
    try:
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["repair-plan-attestation.json is not valid JSON"]
    failures: list[str] = []
    failures.extend(_attestation_signature_failures(attestation, "repair-plan-attestation"))
    if attestation.get("_type") != "https://in-toto.io/Statement/v1":
        failures.append("repair-plan-attestation _type is not https://in-toto.io/Statement/v1")
    if attestation.get("predicateType") != REPAIR_PLAN_ATTESTATION_PREDICATE_TYPE:
        failures.append(f"repair-plan-attestation predicateType is not {REPAIR_PLAN_ATTESTATION_PREDICATE_TYPE}")
    subjects = attestation.get("subject")
    if not isinstance(subjects, list) or not subjects:
        failures.append("repair-plan-attestation subject list missing or empty")
        return failures
    seen = set()
    for subject in subjects:
        if not isinstance(subject, dict):
            failures.append("repair-plan-attestation subject entry is not an object")
            continue
        name = str(subject.get("name", ""))
        if not name:
            failures.append("repair-plan-attestation subject name missing")
            continue
        if name in {"repair-plan-attestation.json", "repair-plan-attestation.md"}:
            failures.append(f"repair-plan-attestation must not include self subject: {name}")
            continue
        if name in seen:
            failures.append(f"repair-plan-attestation duplicate subject: {name}")
        seen.add(name)
        path = output_dir / name
        if not path.exists() or not path.is_file():
            failures.append(f"repair-plan-attestation subject missing from directory: {name}")
            continue
        digest = subject.get("digest")
        expected_sha256 = digest.get("sha256") if isinstance(digest, dict) else ""
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_sha256 != actual:
            failures.append(f"repair-plan-attestation digest mismatch for {name}")
        size_bytes = subject.get("size_bytes")
        if isinstance(size_bytes, int) and size_bytes != path.stat().st_size:
            failures.append(f"repair-plan-attestation size mismatch for {name}")
    for required in ("repair-plan.json", "repair-plan.md"):
        if required not in seen:
            failures.append(f"repair-plan-attestation missing required subject: {required}")
    return failures


def build_repair_eval_artifact_attestation(
    output_dir: str | Path,
    *,
    artifact_type: str,
    required_files: list[str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    payload = payload or _load_json_if_exists(output_dir / required_files[0]) if required_files else {}
    subjects = []
    for path in _named_attested_files(output_dir, required_files):
        subjects.append(_subject_for_path(output_dir, path))
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "predicateType": REPAIR_EVAL_ARTIFACT_ATTESTATION_PREDICATE_TYPE,
        "schema_version": REPAIR_EVAL_ARTIFACT_ATTESTATION_SCHEMA_VERSION,
        "subject": subjects,
        "predicate": {
            "builder": {"id": "metis-agent-harness"},
            "output_dir": str(output_dir),
            "artifact_type": artifact_type,
            "profile": payload.get("profile", "") if isinstance(payload, dict) else "",
            "task_count": payload.get("task_count", payload.get("stub_count", 0)) if isinstance(payload, dict) else 0,
            "schema_version": payload.get("schema_version", "") if isinstance(payload, dict) else "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifact_count": len(subjects),
        },
    }


def write_targeted_eval_stubs_attestation(output_dir: str | Path, *, stubs: dict[str, Any] | None = None) -> Path:
    return _write_repair_eval_artifact_attestation(
        output_dir,
        artifact_type="targeted-eval-stubs",
        required_files=["targeted-eval-stubs.json", "targeted-eval-stubs.md"],
        json_name="targeted-eval-stubs-attestation.json",
        md_name="targeted-eval-stubs-attestation.md",
        payload=stubs,
    )


def write_targeted_eval_suite_attestation(output_dir: str | Path, *, suite: dict[str, Any] | None = None) -> Path:
    return _write_repair_eval_artifact_attestation(
        output_dir,
        artifact_type="targeted-eval-suite",
        required_files=["targeted-eval-suite.json", "targeted-eval-suite.md"],
        json_name="targeted-eval-suite-attestation.json",
        md_name="targeted-eval-suite-attestation.md",
        payload=suite,
    )


def verify_targeted_eval_stubs_attestation(output_dir: str | Path) -> list[str]:
    return _verify_repair_eval_artifact_attestation(
        output_dir,
        artifact_type="targeted-eval-stubs",
        required_files=["targeted-eval-stubs.json", "targeted-eval-stubs.md"],
        json_name="targeted-eval-stubs-attestation.json",
        self_names={"targeted-eval-stubs-attestation.json", "targeted-eval-stubs-attestation.md"},
    )


def verify_targeted_eval_suite_attestation(output_dir: str | Path) -> list[str]:
    return _verify_repair_eval_artifact_attestation(
        output_dir,
        artifact_type="targeted-eval-suite",
        required_files=["targeted-eval-suite.json", "targeted-eval-suite.md"],
        json_name="targeted-eval-suite-attestation.json",
        self_names={"targeted-eval-suite-attestation.json", "targeted-eval-suite-attestation.md"},
    )


def write_repair_execute_preflight_attestation(
    output_dir: str | Path, *, preflight: dict[str, Any] | None = None
) -> Path:
    return _write_repair_eval_artifact_attestation(
        output_dir,
        artifact_type="repair-execute-preflight",
        required_files=["repair-execute-preflight.json", "repair-execute-preflight.md"],
        json_name="repair-execute-preflight-attestation.json",
        md_name="repair-execute-preflight-attestation.md",
        payload=preflight,
    )


def verify_repair_execute_preflight_attestation(output_dir: str | Path) -> list[str]:
    return _verify_repair_eval_artifact_attestation(
        output_dir,
        artifact_type="repair-execute-preflight",
        required_files=["repair-execute-preflight.json", "repair-execute-preflight.md"],
        json_name="repair-execute-preflight-attestation.json",
        self_names={"repair-execute-preflight-attestation.json", "repair-execute-preflight-attestation.md"},
    )


def repair_eval_artifact_attestation_to_markdown(attestation: dict[str, Any]) -> str:
    predicate = attestation.get("predicate", {})
    signature = attestation.get("signature", {})
    lines = [
        "# Metis Repair Eval Artifact Attestation",
        "",
        f"Predicate type: {attestation.get('predicateType', '')}",
        f"Schema version: {attestation.get('schema_version', '')}",
        f"Artifact type: {predicate.get('artifact_type', '')}",
        f"Profile: {predicate.get('profile', '')}",
        f"Task count: {predicate.get('task_count', 0)}",
        f"Artifact count: {predicate.get('artifact_count', 0)}",
        f"Signature: {_signature_markdown_value(signature)}",
        "",
        "| Artifact | SHA256 | Size |",
        "|---|---|---:|",
    ]
    for subject in attestation.get("subject", []):
        digest = subject.get("digest", {}) if isinstance(subject, dict) else {}
        lines.append(f"| {subject.get('name', '')} | {digest.get('sha256', '')} | {subject.get('size_bytes', 0)} |")
    return "\n".join(lines) + "\n"


def repair_plan_attestation_to_markdown(attestation: dict[str, Any]) -> str:
    predicate = attestation.get("predicate", {})
    signature = attestation.get("signature", {})
    lines = [
        "# Metis Repair Plan Attestation",
        "",
        f"Predicate type: {attestation.get('predicateType', '')}",
        f"Schema version: {attestation.get('schema_version', '')}",
        f"Profile: {predicate.get('profile', '')}",
        f"Task count: {predicate.get('task_count', 0)}",
        f"Phase count: {predicate.get('phase_count', 0)}",
        f"Hard preconditions: {', '.join(predicate.get('hard_preconditions', [])) or 'none'}",
        f"Artifact count: {predicate.get('artifact_count', 0)}",
        f"Signature: {_signature_markdown_value(signature)}",
        "",
        "| Artifact | SHA256 | Size |",
        "|---|---|---:|",
    ]
    for subject in attestation.get("subject", []):
        digest = subject.get("digest", {}) if isinstance(subject, dict) else {}
        lines.append(f"| {subject.get('name', '')} | {digest.get('sha256', '')} | {subject.get('size_bytes', 0)} |")
    return "\n".join(lines) + "\n"


def verify_run_attestation(run_dir: str | Path) -> list[str]:
    run_dir = Path(run_dir)
    attestation_path = run_dir / "run-attestation.json"
    if not attestation_path.exists():
        return ["run-attestation.json missing from run directory"]
    try:
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ["run-attestation.json is not valid JSON"]
    failures: list[str] = []
    failures.extend(_attestation_signature_failures(attestation, "run-attestation"))
    if attestation.get("_type") != "https://in-toto.io/Statement/v1":
        failures.append("run-attestation _type is not https://in-toto.io/Statement/v1")
    if attestation.get("predicateType") != RUN_ATTESTATION_PREDICATE_TYPE:
        failures.append(f"run-attestation predicateType is not {RUN_ATTESTATION_PREDICATE_TYPE}")
    subjects = attestation.get("subject")
    if not isinstance(subjects, list) or not subjects:
        failures.append("run-attestation subject list missing or empty")
        return failures
    seen = set()
    for subject in subjects:
        if not isinstance(subject, dict):
            failures.append("run-attestation subject entry is not an object")
            continue
        name = str(subject.get("name", ""))
        if not name:
            failures.append("run-attestation subject name missing")
            continue
        if name in {"run-attestation.json", "run-attestation.md"}:
            failures.append(f"run-attestation must not include self subject: {name}")
            continue
        if name in seen:
            failures.append(f"run-attestation duplicate subject: {name}")
        seen.add(name)
        path = run_dir / name
        if not path.exists() or not path.is_file():
            failures.append(f"run-attestation subject missing from run directory: {name}")
            continue
        digest = subject.get("digest")
        expected_sha256 = digest.get("sha256") if isinstance(digest, dict) else ""
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_sha256 != actual:
            failures.append(f"run-attestation digest mismatch for {name}")
        size_bytes = subject.get("size_bytes")
        if isinstance(size_bytes, int) and size_bytes != path.stat().st_size:
            failures.append(f"run-attestation size mismatch for {name}")
    for required in ("manifest.json", "eval-report.json", "task-specs.json"):
        if required not in seen:
            failures.append(f"run-attestation missing required subject: {required}")
    return failures


def run_attestation_to_markdown(attestation: dict[str, Any]) -> str:
    predicate = attestation.get("predicate", {})
    signature = attestation.get("signature", {})
    lines = [
        "# Metis Run Artifact Attestation",
        "",
        f"Predicate type: {attestation.get('predicateType', '')}",
        f"Schema version: {attestation.get('schema_version', '')}",
        f"Run: {predicate.get('run_name', '')}",
        f"Suite: {predicate.get('suite', '')}",
        f"Artifact count: {predicate.get('artifact_count', 0)}",
        f"Pre-run contract sha256: {predicate.get('pre_run_contract_sha256', '')}",
        f"Provenance hash: {predicate.get('provenance_hash', '')}",
        f"Signature: {_signature_markdown_value(signature)}",
        "",
        "| Artifact | SHA256 | Size |",
        "|---|---|---:|",
    ]
    for subject in attestation.get("subject", []):
        digest = subject.get("digest", {}) if isinstance(subject, dict) else {}
        lines.append(f"| {subject.get('name', '')} | {digest.get('sha256', '')} | {subject.get('size_bytes', 0)} |")
    return "\n".join(lines) + "\n"


def _attested_files(run_dir: Path) -> list[Path]:
    if not run_dir.exists():
        return []
    files = [
        path
        for path in run_dir.rglob("*")
        if path.is_file() and path.name not in {"run-attestation.json", "run-attestation.md"}
    ]
    return sorted(files, key=lambda path: path.relative_to(run_dir).as_posix())


def _repair_plan_attested_files(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return [
        path
        for path in (output_dir / "repair-plan.json", output_dir / "repair-plan.md")
        if path.exists() and path.is_file()
    ]


def _named_attested_files(output_dir: Path, names: list[str]) -> list[Path]:
    if not output_dir.exists():
        return []
    return [path for path in (output_dir / name for name in names) if path.exists() and path.is_file()]


def _write_repair_eval_artifact_attestation(
    output_dir: str | Path,
    *,
    artifact_type: str,
    required_files: list[str],
    json_name: str,
    md_name: str,
    payload: dict[str, Any] | None = None,
) -> Path:
    output_dir = Path(output_dir)
    attestation = build_repair_eval_artifact_attestation(
        output_dir,
        artifact_type=artifact_type,
        required_files=required_files,
        payload=payload,
    )
    _sign_attestation_if_configured(attestation)
    json_path = output_dir / json_name
    md_path = output_dir / md_name
    json_path.write_text(json.dumps(attestation, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(repair_eval_artifact_attestation_to_markdown(attestation), encoding="utf-8")
    return json_path


def _verify_repair_eval_artifact_attestation(
    output_dir: str | Path,
    *,
    artifact_type: str,
    required_files: list[str],
    json_name: str,
    self_names: set[str],
) -> list[str]:
    output_dir = Path(output_dir)
    attestation_path = output_dir / json_name
    if not attestation_path.exists():
        return [f"{json_name} missing from repair eval artifact directory"]
    try:
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [f"{json_name} is not valid JSON"]
    failures: list[str] = []
    failures.extend(_attestation_signature_failures(attestation, json_name))
    if attestation.get("_type") != "https://in-toto.io/Statement/v1":
        failures.append(f"{json_name} _type is not https://in-toto.io/Statement/v1")
    if attestation.get("predicateType") != REPAIR_EVAL_ARTIFACT_ATTESTATION_PREDICATE_TYPE:
        failures.append(f"{json_name} predicateType is not {REPAIR_EVAL_ARTIFACT_ATTESTATION_PREDICATE_TYPE}")
    predicate = attestation.get("predicate", {})
    if not isinstance(predicate, dict) or predicate.get("artifact_type") != artifact_type:
        failures.append(f"{json_name} artifact_type is not {artifact_type}")
    subjects = attestation.get("subject")
    if not isinstance(subjects, list) or not subjects:
        failures.append(f"{json_name} subject list missing or empty")
        return failures
    seen = set()
    for subject in subjects:
        if not isinstance(subject, dict):
            failures.append(f"{json_name} subject entry is not an object")
            continue
        name = str(subject.get("name", ""))
        if not name:
            failures.append(f"{json_name} subject name missing")
            continue
        if name in self_names:
            failures.append(f"{json_name} must not include self subject: {name}")
            continue
        if name in seen:
            failures.append(f"{json_name} duplicate subject: {name}")
        seen.add(name)
        path = output_dir / name
        if not path.exists() or not path.is_file():
            failures.append(f"{json_name} subject missing from directory: {name}")
            continue
        digest = subject.get("digest")
        expected_sha256 = digest.get("sha256") if isinstance(digest, dict) else ""
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected_sha256 != actual:
            failures.append(f"{json_name} digest mismatch for {name}")
        size_bytes = subject.get("size_bytes")
        if isinstance(size_bytes, int) and size_bytes != path.stat().st_size:
            failures.append(f"{json_name} size mismatch for {name}")
    for required in required_files:
        if required not in seen:
            failures.append(f"{json_name} missing required subject: {required}")
    return failures


def _subject_for_path(run_dir: Path, path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "name": path.relative_to(run_dir).as_posix(),
        "digest": {"sha256": hashlib.sha256(raw).hexdigest()},
        "size_bytes": len(raw),
    }


def _sign_attestation_if_configured(attestation: dict[str, Any]) -> None:
    key = os.getenv(ATTESTATION_SIGNING_KEY_ENV)
    if not key:
        return
    attestation.pop("signature", None)
    attestation["signature"] = {
        "algorithm": ATTESTATION_SIGNATURE_ALGORITHM,
        "key_id": _attestation_key_id(key),
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "value": _attestation_signature_value(attestation, key),
    }


def _attestation_signature_failures(attestation: dict[str, Any], label: str) -> list[str]:
    signature = attestation.get("signature")
    if not isinstance(signature, dict):
        if _env_flag(ATTESTATION_REQUIRE_SIGNATURE_ENV):
            return [f"{label} signature missing"]
        return []
    failures: list[str] = []
    key = os.getenv(ATTESTATION_SIGNING_KEY_ENV)
    if not key:
        return [f"{label} signature present but {ATTESTATION_SIGNING_KEY_ENV} is not set"]
    if signature.get("algorithm") != ATTESTATION_SIGNATURE_ALGORITHM:
        failures.append(f"{label} signature algorithm is not {ATTESTATION_SIGNATURE_ALGORITHM}")
    expected_key_id = _attestation_key_id(key)
    if signature.get("key_id") != expected_key_id:
        failures.append(f"{label} signature key_id does not match configured signing key")
    expected_value = _attestation_signature_value(attestation, key)
    actual_value = str(signature.get("value", ""))
    if not hmac.compare_digest(actual_value, expected_value):
        failures.append(f"{label} signature mismatch")
    return failures


def _attestation_signature_value(attestation: dict[str, Any], key: str) -> str:
    return hmac.new(key.encode("utf-8"), _canonical_attestation_payload(attestation), hashlib.sha256).hexdigest()


def _canonical_attestation_payload(attestation: dict[str, Any]) -> bytes:
    unsigned = {name: value for name, value in attestation.items() if name != "signature"}
    return json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _attestation_key_id(key: str) -> str:
    configured = os.getenv(ATTESTATION_KEY_ID_ENV)
    if configured:
        return configured
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _signature_markdown_value(signature: Any) -> str:
    if not isinstance(signature, dict):
        return "none"
    return f"{signature.get('algorithm', '')}:{signature.get('key_id', '')}"


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
