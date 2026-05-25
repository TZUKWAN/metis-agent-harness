import json
import hashlib

from metis.evals.attestation import (
    build_run_attestation,
    run_attestation_to_markdown,
    verify_run_attestation,
    write_run_attestation,
)


def test_build_run_attestation_lists_artifact_digests(tmp_path):
    run_dir = tmp_path / "run"
    failures_dir = run_dir / "failures"
    failures_dir.mkdir(parents=True)
    manifest = {
        "suite": "custom",
        "run_name": "run",
        "task_contract_hash": "task-contract",
        "provenance_hash": "prov",
        "pre_run_contract_path": str(run_dir / "pre-run-contract.json"),
        "pre_run_contract_sha256": "pre-sha",
        "pre_run_provenance_hash": "pre-prov",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "pre-run-contract.json").write_text('{"artifact_type":"test"}', encoding="utf-8")
    (failures_dir / "a.timeline.json").write_text('{"task_id":"a","events":[]}', encoding="utf-8")
    (run_dir / "run-attestation.json").write_text("old", encoding="utf-8")

    attestation = build_run_attestation(run_dir, manifest=manifest)
    markdown = run_attestation_to_markdown(attestation)

    subjects = {subject["name"]: subject for subject in attestation["subject"]}
    assert attestation["_type"] == "https://in-toto.io/Statement/v1"
    assert attestation["predicateType"] == "https://metis.local/attestations/eval-run/v1"
    assert attestation["predicate"]["pre_run_contract_sha256"] == "pre-sha"
    assert "manifest.json" in subjects
    assert "pre-run-contract.json" in subjects
    assert "failures/a.timeline.json" in subjects
    assert "run-attestation.json" not in subjects
    assert subjects["manifest.json"]["digest"]["sha256"] == hashlib.sha256(
        (run_dir / "manifest.json").read_bytes()
    ).hexdigest()
    assert "Metis Run Artifact Attestation" in markdown
    assert "pre-run-contract.json" in markdown


def test_write_run_attestation_writes_json_and_markdown(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text('{"suite":"custom","run_name":"run"}', encoding="utf-8")

    path = write_run_attestation(run_dir)

    assert path == run_dir / "run-attestation.json"
    assert path.exists()
    assert (run_dir / "run-attestation.md").exists()


def test_write_run_attestation_signs_when_key_is_configured(monkeypatch, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text('{"suite":"custom","run_name":"run"}', encoding="utf-8")
    (run_dir / "eval-report.json").write_text("{}", encoding="utf-8")
    (run_dir / "task-specs.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("METIS_ATTESTATION_SIGNING_KEY", "test-signing-key")

    write_run_attestation(run_dir)

    attestation = json.loads((run_dir / "run-attestation.json").read_text(encoding="utf-8"))
    assert attestation["signature"]["algorithm"] == "hmac-sha256-v1"
    assert verify_run_attestation(run_dir) == []
    markdown = (run_dir / "run-attestation.md").read_text(encoding="utf-8")
    assert "Signature: hmac-sha256-v1:" in markdown


def test_verify_run_attestation_rejects_signature_mismatch(monkeypatch, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text('{"suite":"custom","run_name":"run"}', encoding="utf-8")
    (run_dir / "eval-report.json").write_text("{}", encoding="utf-8")
    (run_dir / "task-specs.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("METIS_ATTESTATION_SIGNING_KEY", "test-signing-key")
    write_run_attestation(run_dir)

    monkeypatch.setenv("METIS_ATTESTATION_SIGNING_KEY", "different-signing-key")

    failures = verify_run_attestation(run_dir)

    assert "run-attestation signature key_id does not match configured signing key" in failures
    assert "run-attestation signature mismatch" in failures


def test_verify_run_attestation_can_require_signature(monkeypatch, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text('{"suite":"custom","run_name":"run"}', encoding="utf-8")
    (run_dir / "eval-report.json").write_text("{}", encoding="utf-8")
    (run_dir / "task-specs.json").write_text("[]", encoding="utf-8")
    write_run_attestation(run_dir)
    monkeypatch.setenv("METIS_REQUIRE_ATTESTATION_SIGNATURE", "1")

    failures = verify_run_attestation(run_dir)

    assert "run-attestation signature missing" in failures
