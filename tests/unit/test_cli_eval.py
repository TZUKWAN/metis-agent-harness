import json

from metis.adapters import cli
from metis.evals.runner import EvalResult, EvalSuiteResult
from metis.providers.fake import FakeProvider
from metis.state.sqlite_store import SQLiteStateStore


def test_cli_provider_capabilities_prints_json(capsys):
    exit_code = cli.main(
        [
            "provider",
            "capabilities",
            "--model",
            "glm-4.7-flash",
            "--base-url",
            "https://example.test/v1",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["provider_type"] == "openai_compatible"
    assert payload["model"] == "glm-4.7-flash"
    assert payload["native_tool_calling"] is True
    assert payload["thinking"] is True


def test_cli_checkpoint_latest_prints_json(tmp_path, capsys):
    state_db = tmp_path / "state.db"
    store = SQLiteStateStore(state_db)
    store.create_session("s1")
    store.record_checkpoint(
        "s1",
        phase="agent.start",
        status="started",
        task_contract_hash="contract",
        prompt_stack_hash="prompt",
        metadata={"turn": 0},
    )

    exit_code = cli.main(["checkpoint", "latest", "--state-db", str(state_db), "--session-id", "s1", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["checkpoint"]["phase"] == "agent.start"
    assert payload["checkpoint"]["task_contract_hash"] == "contract"
    assert payload["checkpoint"]["metadata"] == {"turn": 0}


def test_cli_checkpoint_list_prints_json(tmp_path, capsys):
    state_db = tmp_path / "state.db"
    store = SQLiteStateStore(state_db)
    store.create_session("s1")
    store.record_checkpoint("s1", phase="agent.start", status="started")
    store.record_checkpoint("s1", phase="agent.finalization", status="final")

    exit_code = cli.main(["checkpoint", "list", "--state-db", str(state_db), "--session-id", "s1", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert [item["phase"] for item in payload["checkpoints"]] == ["agent.start", "agent.finalization"]


def test_cli_checkpoint_latest_returns_nonzero_when_missing(tmp_path, capsys):
    state_db = tmp_path / "state.db"
    SQLiteStateStore(state_db)

    exit_code = cli.main(["checkpoint", "latest", "--state-db", str(state_db), "--session-id", "missing", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["checkpoint"] is None


def test_cli_resume_continues_persisted_session(monkeypatch, tmp_path, capsys):
    state_db = tmp_path / "state.db"
    store = SQLiteStateStore(state_db)
    store.create_session("s1")
    store.append_message("s1", "system", "system prompt")
    store.append_message("s1", "user", "original task")
    monkeypatch.setattr(
        cli,
        "OpenAICompatibleProvider",
        lambda **kwargs: FakeProvider(
            [
                {
                    "content": json.dumps(
                        {
                            "status": "done",
                            "summary": "resumed answer",
                            "evidence_refs": [],
                            "artifact_refs": [],
                            "next_action": "",
                        }
                    ),
                    "finish_reason": "stop",
                }
            ]
        ),
    )

    exit_code = cli.main(
        [
            "resume",
            "--state-db",
            str(state_db),
            "--session-id",
            "s1",
            "--message",
            "continue",
            "--workspace",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    resumed_store = SQLiteStateStore(state_db)
    messages = resumed_store.list_messages("s1")
    latest = resumed_store.latest_checkpoint("s1")
    assert exit_code == 0
    assert "resumed answer" in captured.out
    assert [message["content"] for message in messages].count("original task") == 1
    assert any(message["content"] == "continue" and message["metadata"]["source"] == "resume" for message in messages)
    assert latest["phase"] == "agent.finalization"
    checkpoints = resumed_store.list_checkpoints("s1")
    assert any(checkpoint["phase"] == "agent.resume" for checkpoint in checkpoints)


def test_cli_run_can_persist_state_when_state_db_is_enabled(monkeypatch, tmp_path, capsys):
    state_db = tmp_path / "run-state.db"
    monkeypatch.setattr(
        cli,
        "OpenAICompatibleProvider",
        lambda **kwargs: FakeProvider(
            [
                {
                    "content": json.dumps(
                        {
                            "status": "done",
                            "summary": "persisted run",
                            "evidence_refs": [],
                            "artifact_refs": [],
                            "next_action": "",
                        }
                    ),
                    "finish_reason": "stop",
                }
            ]
        ),
    )

    exit_code = cli.main(
        [
            "run",
            "do persistent work",
            "--workspace",
            str(tmp_path),
            "--state-db",
            str(state_db),
            "--session-id",
            "run-session",
        ]
    )

    captured = capsys.readouterr()
    store = SQLiteStateStore(state_db)
    messages = store.list_messages("run-session")
    checkpoints = store.list_checkpoints("run-session")
    assert exit_code == 0
    assert "persisted run" in captured.out
    assert any(message["content"] == "do persistent work" for message in messages)
    assert any(checkpoint["phase"] == "agent.start" for checkpoint in checkpoints)


def test_cli_resume_returns_nonzero_without_persisted_messages(tmp_path, capsys):
    state_db = tmp_path / "state.db"
    SQLiteStateStore(state_db)

    exit_code = cli.main(
        [
            "resume",
            "--state-db",
            str(state_db),
            "--session-id",
            "missing",
            "--message",
            "continue",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No persisted messages found for session: missing" in captured.err


def test_cli_app_init_and_show_manifest(tmp_path, capsys):
    manifest_path = tmp_path / "metis-agent.json"

    init_exit = cli.main(["app", "init", "--name", "Acme Analyst", "--output", str(manifest_path)])
    show_exit = cli.main(["app", "show", "--manifest", str(manifest_path)])

    captured = capsys.readouterr()
    assert init_exit == 0
    assert show_exit == 0
    assert manifest_path.exists()
    assert "Acme Analyst" in captured.out


def test_cli_develop_writes_reports_without_approval(tmp_path, capsys):
    output_dir = tmp_path / "dev"

    exit_code = cli.main(
        [
            "develop",
            "--request",
            "Build a grant writing agent.",
            "--name",
            "Grant Builder",
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"approved": false' in captured.out
    assert (output_dir / "analysis-report.md").exists()
    assert (output_dir / "adaptation-plan.md").exists()
    assert (output_dir / "task-breakdown.md").exists()
    assert (output_dir / "implementation-contract.md").exists()
    assert (output_dir / "verification-checklist.md").exists()
    assert (output_dir / "task-contract.md").exists()
    assert not (output_dir / "metis-agent.json").exists()


def test_cli_develop_approve_writes_brand_commands_and_tasks(tmp_path, capsys):
    output_dir = tmp_path / "dev"

    exit_code = cli.main(
        [
            "develop",
            "--request",
            "Build a grant writing agent.",
            "--name",
            "Grant Builder",
            "--output-dir",
            str(output_dir),
            "--approve",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Approved artifacts written: true" in captured.out
    assert (output_dir / "metis-agent.json").exists()
    assert (output_dir / "README.md").exists()
    assert (output_dir / "branding.json").exists()
    assert (output_dir / ".claude" / "commands" / "grant-builder.md").exists()
    assert (output_dir / ".codex" / "commands" / "grant-builder.md").exists()
    assert (output_dir / "metis-dev-tasks.json").exists()


def test_cli_develop_infers_name_from_request_in_noninteractive_mode(tmp_path, capsys):
    output_dir = tmp_path / "dev"

    exit_code = cli.main(
        [
            "develop",
            "--request",
            "Build an agent called Grant Builder for nonprofit proposals.",
            "--output-dir",
            str(output_dir),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"app_name": "Grant Builder"' in captured.out


def test_cli_develop_approve_json_infers_name_without_prompting(tmp_path, capsys):
    output_dir = tmp_path / "dev"

    exit_code = cli.main(
        [
            "develop",
            "--request",
            "Build an agent called Grant Builder for nonprofit proposals.",
            "--output-dir",
            str(output_dir),
            "--approve",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"approved": true' in captured.out
    assert '"app_name": "Grant Builder"' in captured.out
    assert (output_dir / "metis-agent.json").exists()


def test_cli_package_build_and_verify(tmp_path, capsys):
    source = tmp_path / "source"
    prompts = source / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "agent-system.md").write_text("system", encoding="utf-8")
    (prompts / "agent-developer.md").write_text("developer", encoding="utf-8")
    (source / "README.md").write_text("# Agent", encoding="utf-8")
    (source / "metis-agent.json").write_text(
        json.dumps(
            {
                "name": "Agent",
                "workspace": ".",
                "model": "glm-4.7-flash",
                "profile": "small",
                "system_prompt_path": "prompts/agent-system.md",
                "developer_prompt_path": "prompts/agent-developer.md",
            }
        ),
        encoding="utf-8",
    )
    package_dir = tmp_path / "package"

    build_exit = cli.main(["package", "build", "--source", str(source), "--output", str(package_dir)])
    verify_exit = cli.main(["package", "verify", "--path", str(package_dir), "--profile", "dev", "--json"])

    captured = capsys.readouterr()
    assert build_exit == 0
    assert verify_exit == 0
    assert (package_dir / "metis-package.json").exists()
    assert '"valid": true' in captured.out


def test_cli_package_install_and_export(tmp_path, capsys):
    source = tmp_path / "source"
    prompts = source / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "agent-system.md").write_text("system", encoding="utf-8")
    (prompts / "agent-developer.md").write_text("developer", encoding="utf-8")
    (source / "README.md").write_text("# Agent", encoding="utf-8")
    (source / "metis-agent.json").write_text(
        json.dumps(
            {
                "name": "Agent",
                "workspace": ".",
                "model": "glm-4.7-flash",
                "profile": "small",
                "system_prompt_path": "prompts/agent-system.md",
                "developer_prompt_path": "prompts/agent-developer.md",
            }
        ),
        encoding="utf-8",
    )
    package_dir = tmp_path / "package"
    cli.main(["package", "build", "--source", str(source), "--output", str(package_dir)])

    install_exit = cli.main(["package", "install", "--path", str(package_dir), "--install-dir", str(tmp_path / "installed")])
    export_exit = cli.main(["package", "export", "--path", str(package_dir), "--output", str(tmp_path / "agent.zip")])

    assert install_exit == 0
    assert export_exit == 0
    assert (tmp_path / "installed" / "metis-agent.json").exists()
    assert (tmp_path / "agent.zip").exists()


def test_cli_real_small_model_eval_refuses_to_fake_without_endpoint(monkeypatch, capsys):
    monkeypatch.setattr(cli, "real_model_env_configured", lambda: False)

    exit_code = cli.main(["eval", "real-small-model"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "requires METIS_BASE_URL, METIS_API_KEY, and METIS_MODEL" in captured.out
    assert "no model result was faked" in captured.out


def test_cli_real_small_model_eval_writes_reports_when_endpoint_configured(monkeypatch, tmp_path, capsys):
    run_calls = []
    write_calls = []
    report_dir = tmp_path / "docs" / "evals" / "runs" / "20260525-010203"
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ],
        metadata={"suite": "real-small-model", "task_count": 1},
    )

    async def fake_run(*, workspace):
        run_calls.append({"workspace": workspace})
        return suite

    def fake_write(actual_suite, *, output_root, run_name):
        write_calls.append({"suite": actual_suite, "output_root": output_root, "run_name": run_name})
        return report_dir

    monkeypatch.setattr(cli, "real_model_env_configured", lambda: True)
    monkeypatch.setattr(cli, "run_real_small_model_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_real_small_model_eval_reports", fake_write)

    exit_code = cli.main(
        [
            "eval",
            "real-small-model",
            "--workspace",
            str(tmp_path / "workspace"),
            "--output-root",
            str(tmp_path),
            "--run-name",
            "latest",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert run_calls == [{"workspace": str(tmp_path / "workspace")}]
    assert write_calls == [{"suite": suite, "output_root": str(tmp_path), "run_name": "latest"}]
    assert "success_rate=100.00%" in captured.out
    assert str(report_dir) in captured.out


def test_cli_real_small_model_eval_defaults_to_auto_run_name(monkeypatch, tmp_path):
    run_names = []
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ]
    )

    async def fake_run(*, workspace):
        return suite

    def fake_write(actual_suite, *, output_root, run_name):
        run_names.append(run_name)
        return tmp_path / "docs" / "evals" / "runs" / "20260525-010203"

    monkeypatch.setattr(cli, "real_model_env_configured", lambda: True)
    monkeypatch.setattr(cli, "resolve_real_small_model_eval_run_name", lambda run_name: "20260525-010203")
    monkeypatch.setattr(cli, "run_real_small_model_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_real_small_model_eval_reports", fake_write)

    exit_code = cli.main(["eval", "real-small-model", "--output-root", str(tmp_path)])

    assert exit_code == 0
    assert run_names == ["20260525-010203"]


def test_cli_real_small_model_eval_can_run_gate_after_report_write(monkeypatch, tmp_path, capsys):
    report_dir = tmp_path / "docs" / "evals" / "runs" / "20260525-010203"
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="strict-final-no-tools",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ]
    )
    gate = {
        "passed": True,
        "run": {"run_name": "20260525-010203", "run_dir": str(report_dir), "success_rate": 1.0},
        "thresholds": {},
        "aggregates": {},
        "failed_tasks": [],
        "failures": [],
    }
    gate_calls = []

    async def fake_run(*, workspace):
        return suite

    monkeypatch.setattr(cli, "real_model_env_configured", lambda: True)
    monkeypatch.setattr(cli, "run_real_small_model_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_real_small_model_eval_reports", lambda actual, *, output_root, run_name: report_dir)
    monkeypatch.setattr(cli, "evaluate_eval_run_gate", lambda run: gate_calls.append(run) or gate)
    monkeypatch.setattr(cli, "write_eval_gate_report", lambda actual, output_dir: gate_calls.append(output_dir))

    exit_code = cli.main(["eval", "real-small-model", "--output-root", str(tmp_path), "--gate"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert gate_calls == [report_dir, str(report_dir / "gate")]
    assert "Passed: True" in captured.out
    assert "Gate written to:" in captured.out


def test_cli_real_small_model_eval_can_compare_explicit_baseline(monkeypatch, tmp_path, capsys):
    report_dir = tmp_path / "docs" / "evals" / "runs" / "20260525-010203"
    baseline_dir = tmp_path / "docs" / "evals" / "runs" / "baseline"
    comparison = {
        "has_regression": False,
        "baseline": {"run_name": "baseline", "run_dir": str(baseline_dir)},
        "current": {"run_name": "20260525-010203", "run_dir": str(report_dir)},
        "success_rate_delta": 0.0,
        "newly_failed_tasks": [],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    compare_calls = []
    suite = EvalSuiteResult(
        [EvalResult(task_id="strict-final-no-tools", success=True, status="final", turns_used=1, tool_calls=0, latency_seconds=0.01)]
    )

    async def fake_run(*, workspace):
        return suite

    def fake_compare(*, baseline_dir, current_dir, profile):
        compare_calls.append({"baseline_dir": baseline_dir, "current_dir": current_dir, "profile": profile})
        return comparison

    monkeypatch.setattr(cli, "real_model_env_configured", lambda: True)
    monkeypatch.setattr(cli, "run_real_small_model_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_real_small_model_eval_reports", lambda actual, *, output_root, run_name: report_dir)
    monkeypatch.setattr(cli, "compare_eval_runs", fake_compare)
    monkeypatch.setattr(cli, "write_eval_run_comparison", lambda actual, output_dir: compare_calls.append({"output_dir": output_dir}))

    exit_code = cli.main(
        [
            "eval",
            "real-small-model",
            "--output-root",
            str(tmp_path),
            "--compare-baseline",
            str(baseline_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert compare_calls == [
        {"baseline_dir": str(baseline_dir), "current_dir": report_dir, "profile": "release"},
        {"output_dir": str(report_dir / "comparison")},
    ]
    assert "Has regression: False" in captured.out


def test_cli_real_small_model_eval_compare_latest_uses_previous_pointer(monkeypatch, tmp_path, capsys):
    runs_root = tmp_path / "docs" / "evals" / "runs"
    previous_dir = runs_root / "previous"
    current_dir = runs_root / "current"
    runs_root.mkdir(parents=True)
    (runs_root / "latest.json").write_text(
        '{"latest_run_dir": "' + str(previous_dir).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    comparison = {
        "has_regression": True,
        "baseline": {"run_name": "previous", "run_dir": str(previous_dir)},
        "current": {"run_name": "current", "run_dir": str(current_dir)},
        "success_rate_delta": -1.0,
        "newly_failed_tasks": ["a"],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    compare_calls = []
    suite = EvalSuiteResult(
        [EvalResult(task_id="strict-final-no-tools", success=True, status="final", turns_used=1, tool_calls=0, latency_seconds=0.01)]
    )

    async def fake_run(*, workspace):
        return suite

    def fake_compare(*, baseline_dir, current_dir, profile):
        compare_calls.append({"baseline_dir": baseline_dir, "current_dir": current_dir, "profile": profile})
        return comparison

    monkeypatch.setattr(cli, "real_model_env_configured", lambda: True)
    monkeypatch.setattr(cli, "run_real_small_model_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_real_small_model_eval_reports", lambda actual, *, output_root, run_name: current_dir)
    monkeypatch.setattr(cli, "compare_eval_runs", fake_compare)
    monkeypatch.setattr(cli, "write_eval_run_comparison", lambda actual, output_dir: None)

    exit_code = cli.main(["eval", "real-small-model", "--output-root", str(tmp_path), "--compare-latest"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert compare_calls == [{"baseline_dir": str(previous_dir), "current_dir": current_dir, "profile": "release"}]
    assert "Has regression: True" in captured.out


def test_cli_real_small_model_eval_passes_compare_profile(monkeypatch, tmp_path):
    report_dir = tmp_path / "docs" / "evals" / "runs" / "20260525-010203"
    baseline_dir = tmp_path / "docs" / "evals" / "runs" / "baseline"
    comparison = {
        "profile": "strict",
        "has_regression": True,
        "regression_reasons": ["new_clusters"],
        "baseline": {"run_name": "baseline", "run_dir": str(baseline_dir)},
        "current": {"run_name": "20260525-010203", "run_dir": str(report_dir)},
        "success_rate_delta": 0.0,
        "newly_failed_tasks": [],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    compare_calls = []
    suite = EvalSuiteResult(
        [EvalResult(task_id="strict-final-no-tools", success=True, status="final", turns_used=1, tool_calls=0, latency_seconds=0.01)]
    )

    async def fake_run(*, workspace):
        return suite

    def fake_compare(*, baseline_dir, current_dir, profile):
        compare_calls.append({"baseline_dir": baseline_dir, "current_dir": current_dir, "profile": profile})
        return comparison

    monkeypatch.setattr(cli, "real_model_env_configured", lambda: True)
    monkeypatch.setattr(cli, "run_real_small_model_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_real_small_model_eval_reports", lambda actual, *, output_root, run_name: report_dir)
    monkeypatch.setattr(cli, "compare_eval_runs", fake_compare)
    monkeypatch.setattr(cli, "write_eval_run_comparison", lambda actual, output_dir: None)

    exit_code = cli.main(
        [
            "eval",
            "real-small-model",
            "--output-root",
            str(tmp_path),
            "--compare-baseline",
            str(baseline_dir),
            "--compare-profile",
            "strict",
        ]
    )

    assert exit_code == 1
    assert compare_calls == [{"baseline_dir": str(baseline_dir), "current_dir": report_dir, "profile": "strict"}]


def test_cli_real_small_model_eval_compare_latest_fails_without_previous_pointer(monkeypatch, tmp_path, capsys):
    suite = EvalSuiteResult(
        [EvalResult(task_id="strict-final-no-tools", success=True, status="final", turns_used=1, tool_calls=0, latency_seconds=0.01)]
    )

    async def fake_run(*, workspace):
        return suite

    monkeypatch.setattr(cli, "real_model_env_configured", lambda: True)
    monkeypatch.setattr(cli, "run_real_small_model_eval_suite", fake_run)
    monkeypatch.setattr(
        cli,
        "write_real_small_model_eval_reports",
        lambda actual, *, output_root, run_name: tmp_path / "docs" / "evals" / "runs" / "current",
    )

    exit_code = cli.main(["eval", "real-small-model", "--output-root", str(tmp_path), "--compare-latest"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Cannot compare latest" in captured.out


def test_cli_eval_compare_returns_nonzero_when_regressed(monkeypatch, tmp_path, capsys):
    comparison = {
        "has_regression": True,
        "baseline": {"run_name": "base", "run_dir": "base"},
        "current": {"run_name": "current", "run_dir": "current"},
        "success_rate_delta": -0.5,
        "newly_failed_tasks": ["a"],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    calls = []

    def fake_compare(*, baseline_dir, current_dir, profile):
        calls.append({"baseline_dir": baseline_dir, "current_dir": current_dir, "profile": profile})
        return comparison

    monkeypatch.setattr(cli, "compare_eval_runs", fake_compare)

    exit_code = cli.main(["eval", "compare", "--baseline", "base", "--current", "current"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls == [{"baseline_dir": "base", "current_dir": "current", "profile": "release"}]
    assert "Has regression: True" in captured.out


def test_cli_eval_compare_profile_controls_exit_code(monkeypatch, capsys):
    comparison = {
        "profile": "exploratory",
        "has_regression": False,
        "regression_reasons": [],
        "baseline": {"run_name": "base", "run_dir": "base"},
        "current": {"run_name": "current", "run_dir": "current"},
        "success_rate_delta": -0.5,
        "newly_failed_tasks": ["a"],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    calls = []

    def fake_compare(*, baseline_dir, current_dir, profile):
        calls.append({"baseline_dir": baseline_dir, "current_dir": current_dir, "profile": profile})
        return comparison

    monkeypatch.setattr(cli, "compare_eval_runs", fake_compare)

    exit_code = cli.main(["eval", "compare", "--baseline", "base", "--current", "current", "--profile", "exploratory"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [{"baseline_dir": "base", "current_dir": "current", "profile": "exploratory"}]
    assert "Profile: exploratory" in captured.out


def test_cli_eval_compare_can_write_output_and_print_json(monkeypatch, tmp_path, capsys):
    comparison = {
        "has_regression": False,
        "baseline": {"run_name": "base", "run_dir": "base"},
        "current": {"run_name": "current", "run_dir": "current"},
        "success_rate_delta": 0.0,
        "newly_failed_tasks": [],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    output_calls = []

    monkeypatch.setattr(cli, "compare_eval_runs", lambda *, baseline_dir, current_dir, profile: comparison)
    monkeypatch.setattr(cli, "write_eval_run_comparison", lambda actual, output_dir: output_calls.append((actual, output_dir)))

    exit_code = cli.main(
        [
            "eval",
            "compare",
            "--baseline",
            "base",
            "--current",
            "current",
            "--output-dir",
            str(tmp_path),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_calls == [(comparison, str(tmp_path))]
    assert '"has_regression": false' in captured.out


def test_cli_eval_diagnose_writes_repair_tasks(monkeypatch, tmp_path, capsys):
    repair_tasks = {
        "profile": "release",
        "task_count": 1,
        "tasks": [{"id": "repair-001", "reason": "newly_failed_tasks"}],
    }
    calls = []

    def fake_diagnose(comparison, output_dir):
        calls.append({"comparison": comparison, "output_dir": output_dir})
        return repair_tasks

    monkeypatch.setattr(cli, "diagnose_eval_comparison", fake_diagnose)

    exit_code = cli.main(
        [
            "eval",
            "diagnose",
            "--comparison",
            str(tmp_path / "comparison"),
            "--output-dir",
            str(tmp_path / "repair"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [{"comparison": str(tmp_path / "comparison"), "output_dir": str(tmp_path / "repair")}]
    assert "Metis Repair Tasks" in captured.out
    assert "repair-001" in captured.out


def test_cli_eval_diagnose_can_print_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "diagnose_eval_comparison",
        lambda comparison, output_dir: {"profile": "release", "task_count": 0, "tasks": []},
    )

    exit_code = cli.main(["eval", "diagnose", "--comparison", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"task_count": 0' in captured.out


def test_cli_eval_repair_plan_writes_plan(monkeypatch, tmp_path, capsys):
    plan = {
        "profile": "release",
        "task_count": 1,
        "priority_buckets": {"high": ["repair-001"]},
        "phases": [],
        "owner_areas": [],
        "next_actions": ["Fix repair-001."],
    }
    calls = []

    def fake_plan_repairs(repair_tasks):
        calls.append({"repair_tasks": repair_tasks})
        return plan

    def fake_write_repair_plan(actual_plan, output_dir):
        calls.append({"plan": actual_plan, "output_dir": output_dir})

    monkeypatch.setattr(cli, "plan_repairs", fake_plan_repairs)
    monkeypatch.setattr(cli, "write_repair_plan", fake_write_repair_plan)

    exit_code = cli.main(
        [
            "eval",
            "repair-plan",
            "--repair-tasks",
            str(tmp_path / "repair-tasks.json"),
            "--output-dir",
            str(tmp_path / "plan"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        {"repair_tasks": str(tmp_path / "repair-tasks.json")},
        {"plan": plan, "output_dir": str(tmp_path / "plan")},
    ]
    assert "Metis Repair Plan" in captured.out
    assert "repair-001" in captured.out


def test_cli_eval_repair_plan_can_print_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "plan_repairs",
        lambda repair_tasks: {"profile": "release", "task_count": 0, "priority_buckets": {}, "phases": []},
    )

    exit_code = cli.main(["eval", "repair-plan", "--repair-tasks", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"task_count": 0' in captured.out


def test_cli_eval_repair_plan_rejects_blocked_required_phase(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "plan_repairs",
        lambda repair_tasks: {
            "profile": "release",
            "task_count": 2,
            "priority_buckets": {},
            "phase_status_summary": {
                "executable_phases": ["phase-0b-repair-suite-hygiene"],
                "blocked_phases": ["phase-1-stop-release-blockers"],
            },
            "phases": [
                {
                    "id": "phase-0b-repair-suite-hygiene",
                    "title": "Repair suite hygiene",
                    "status": "open",
                    "blocked_by": [],
                    "task_ids": ["repair-001"],
                    "task_count": 1,
                },
                {
                    "id": "phase-1-stop-release-blockers",
                    "title": "Stop release blockers",
                    "status": "blocked",
                    "blocked_by": ["phase-0b-repair-suite-hygiene"],
                    "task_ids": ["repair-002"],
                    "task_count": 1,
                },
            ],
        },
    )
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda output_dir: [])

    exit_code = cli.main(
        [
            "eval",
            "repair-plan",
            "--repair-tasks",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "plan"),
            "--require-executable-phase",
            "phase-1-stop-release-blockers",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Metis Repair Plan" in captured.out
    assert "Required repair phase is not executable: phase-1-stop-release-blockers" in captured.err
    assert "blocked_by=phase-0b-repair-suite-hygiene" in captured.err


def test_cli_eval_repair_plan_accepts_executable_required_phase(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "plan_repairs",
        lambda repair_tasks: {
            "profile": "release",
            "task_count": 1,
            "priority_buckets": {},
            "phase_status_summary": {"executable_phases": ["phase-1-stop-release-blockers"]},
            "phases": [
                {
                    "id": "phase-1-stop-release-blockers",
                    "title": "Stop release blockers",
                    "status": "open",
                    "blocked_by": [],
                    "task_ids": ["repair-001"],
                    "task_count": 1,
                }
            ],
        },
    )
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda output_dir: [])

    exit_code = cli.main(
        [
            "eval",
            "repair-plan",
            "--repair-tasks",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "plan"),
            "--require-executable-phase",
            "phase-1-stop-release-blockers",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Stop release blockers" in captured.out
    assert captured.err == ""


def test_cli_eval_repair_plan_requires_output_dir_for_phase_enforcement(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "plan_repairs",
        lambda repair_tasks: {
            "profile": "release",
            "task_count": 0,
            "priority_buckets": {},
            "phase_status_summary": {"executable_phases": []},
            "phases": [],
        },
    )

    exit_code = cli.main(
        [
            "eval",
            "repair-plan",
            "--repair-tasks",
            str(tmp_path),
            "--require-executable-phase",
            "phase-1-stop-release-blockers",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "requires --output-dir" in captured.err


def test_cli_eval_repair_plan_rejects_failed_attestation(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "plan_repairs",
        lambda repair_tasks: {
            "profile": "release",
            "task_count": 1,
            "priority_buckets": {},
            "phase_status_summary": {"executable_phases": ["phase-1-stop-release-blockers"]},
            "phases": [
                {
                    "id": "phase-1-stop-release-blockers",
                    "title": "Stop release blockers",
                    "status": "open",
                    "blocked_by": [],
                    "task_ids": ["repair-001"],
                    "task_count": 1,
                }
            ],
        },
    )
    monkeypatch.setattr(
        cli,
        "verify_repair_plan_attestation",
        lambda output_dir: ["repair-plan-attestation digest mismatch for repair-plan.json"],
    )

    exit_code = cli.main(
        [
            "eval",
            "repair-plan",
            "--repair-tasks",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "plan"),
            "--require-executable-phase",
            "phase-1-stop-release-blockers",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Repair plan attestation failed: repair-plan-attestation digest mismatch for repair-plan.json" in captured.err


def test_cli_eval_verify_repair_plan_prints_markdown_and_returns_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda plan_dir: [])

    exit_code = cli.main(["eval", "verify-repair-plan", "--plan-dir", str(tmp_path / "plan")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metis Repair Plan Verification" in captured.out
    assert "Artifact: repair_plan" in captured.out
    assert "Verified: true" in captured.out
    assert "Failure count: 0" in captured.out
    assert "- None" in captured.out


def test_cli_eval_verify_repair_plan_prints_json_and_returns_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "verify_repair_plan_attestation",
        lambda plan_dir: ["repair-plan-attestation digest mismatch for repair-plan.md"],
    )

    exit_code = cli.main(["eval", "verify-repair-plan", "--plan-dir", str(tmp_path / "plan"), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"verified": false' in captured.out
    assert '"failure_count": 1' in captured.out
    assert "repair-plan-attestation digest mismatch for repair-plan.md" in captured.out


def test_cli_eval_verify_eval_stubs_prints_markdown_and_returns_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "verify_targeted_eval_stubs_attestation", lambda stubs_dir: [])

    exit_code = cli.main(["eval", "verify-eval-stubs", "--stubs-dir", str(tmp_path / "stubs")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metis Targeted Eval Stubs Verification" in captured.out
    assert "Artifact: targeted_eval_stubs" in captured.out
    assert "Verified: true" in captured.out


def test_cli_eval_verify_eval_stubs_prints_json_and_returns_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "verify_targeted_eval_stubs_attestation",
        lambda stubs_dir: ["targeted-eval-stubs-attestation.json digest mismatch for targeted-eval-stubs.md"],
    )

    exit_code = cli.main(["eval", "verify-eval-stubs", "--stubs-dir", str(tmp_path / "stubs"), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"artifact": "targeted_eval_stubs"' in captured.out
    assert '"verified": false' in captured.out
    assert "targeted-eval-stubs-attestation.json digest mismatch for targeted-eval-stubs.md" in captured.out


def test_cli_eval_verify_targeted_suite_prints_markdown_and_returns_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "verify_targeted_eval_suite_attestation", lambda suite_dir: [])

    exit_code = cli.main(["eval", "verify-targeted-suite", "--suite-dir", str(tmp_path / "suite")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metis Targeted Eval Suite Verification" in captured.out
    assert "Artifact: targeted_eval_suite" in captured.out
    assert "Verified: true" in captured.out


def test_cli_eval_verify_targeted_suite_prints_json_and_returns_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "verify_targeted_eval_suite_attestation",
        lambda suite_dir: ["targeted-eval-suite-attestation.json digest mismatch for targeted-eval-suite.json"],
    )

    exit_code = cli.main(["eval", "verify-targeted-suite", "--suite-dir", str(tmp_path / "suite"), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"artifact": "targeted_eval_suite"' in captured.out
    assert '"verified": false' in captured.out
    assert "targeted-eval-suite-attestation.json digest mismatch for targeted-eval-suite.json" in captured.out


def test_cli_eval_repair_execute_preflight_passes_verified_artifacts(monkeypatch, tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    stubs_dir = tmp_path / "stubs"
    suite_dir = tmp_path / "suite"
    plan_dir.mkdir()
    stubs_dir.mkdir()
    suite_dir.mkdir()
    (plan_dir / "repair-plan.json").write_text(
        json.dumps(
            {
                "phase_status_summary": {"executable_phases": ["phase-1-stop-release-blockers"]},
                "phases": [
                    {
                        "id": "phase-1-stop-release-blockers",
                        "status": "open",
                        "blocked_by": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda actual: calls.append(("plan", str(actual))) or [])
    monkeypatch.setattr(cli, "verify_targeted_eval_stubs_attestation", lambda actual: calls.append(("stubs", str(actual))) or [])
    monkeypatch.setattr(cli, "verify_targeted_eval_suite_attestation", lambda actual: calls.append(("suite", str(actual))) or [])

    exit_code = cli.main(
        [
            "eval",
            "repair-execute",
            "--plan-dir",
            str(plan_dir),
            "--phase",
            "phase-1-stop-release-blockers",
            "--stubs-dir",
            str(stubs_dir),
            "--suite-dir",
            str(suite_dir),
            "--output-dir",
            str(tmp_path / "preflight"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metis Repair Execute Preflight" in captured.out
    assert "Ready: true" in captured.out
    assert (tmp_path / "preflight" / "repair-execute-preflight.json").exists()
    assert (tmp_path / "preflight" / "repair-execute-preflight.md").exists()
    assert (tmp_path / "preflight" / "repair-execute-preflight-attestation.json").exists()
    assert (tmp_path / "preflight" / "repair-execute-preflight-attestation.md").exists()
    written = json.loads((tmp_path / "preflight" / "repair-execute-preflight.json").read_text(encoding="utf-8"))
    assert written["ready"] is True
    assert written["phase"] == "phase-1-stop-release-blockers"
    assert calls == [("plan", str(plan_dir)), ("stubs", str(stubs_dir)), ("suite", str(suite_dir))]


def test_cli_eval_repair_execute_records_attempt_and_updated_plan(monkeypatch, tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "repair-plan.json").write_text(
        json.dumps(
            {
                "profile": "release",
                "task_count": 1,
                "tasks": [
                    {
                        "id": "repair-001",
                        "reason": "newly_failed_tasks",
                        "priority": "high",
                        "owner_area": "runtime-loop",
                        "suggested_eval": "Add regression eval.",
                    }
                ],
                "phase_status_summary": {"executable_phases": ["phase-1-stop-release-blockers"]},
                "phases": [
                    {
                        "id": "phase-1-stop-release-blockers",
                        "status": "open",
                        "blocked_by": [],
                        "task_ids": ["repair-001"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda actual: [])

    output_dir = tmp_path / "preflight"
    exit_code = cli.main(
        [
            "eval",
            "repair-execute",
            "--plan-dir",
            str(plan_dir),
            "--phase",
            "phase-1-stop-release-blockers",
            "--output-dir",
            str(output_dir),
            "--record-attempt-status",
            "in_progress",
            "--executor-id",
            "unit-test-executor",
            "--attempt-note",
            "claiming work",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ready: true" in captured.out
    attempt = json.loads((output_dir / "repair-execute-attempt" / "repair-execute-attempt.json").read_text(encoding="utf-8"))
    assert attempt["status"] == "in_progress"
    assert attempt["executor_id"] == "unit-test-executor"
    updated = json.loads((output_dir / "updated-repair-plan" / "repair-plan.json").read_text(encoding="utf-8"))
    assert updated["tasks"][0]["status"] == "in_progress"
    assert updated["tasks"][0]["last_attempt"]["executor_id"] == "unit-test-executor"
    phase = next(item for item in updated["phases"] if item["id"] == "phase-1-stop-release-blockers")
    assert phase["status"] == "in_progress"
    assert phase["last_attempt"]["status"] == "in_progress"
    assert (output_dir / "updated-repair-plan" / "repair-plan-attestation.json").exists()


def test_cli_eval_repair_execute_runs_declared_safe_commands(monkeypatch, tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "repair-plan.json").write_text(
        json.dumps(
            {
                "profile": "release",
                "task_count": 1,
                "tasks": [
                    {
                        "id": "repair-001",
                        "status": "open",
                        "execution_commands": [["python", "--version"]],
                    }
                ],
                "phase_status_summary": {"executable_phases": ["phase-1-stop-release-blockers"]},
                "phases": [
                    {
                        "id": "phase-1-stop-release-blockers",
                        "status": "open",
                        "blocked_by": [],
                        "task_ids": ["repair-001"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda actual: [])

    output_dir = tmp_path / "execute"
    exit_code = cli.main(
        [
            "eval",
            "repair-execute",
            "--plan-dir",
            str(plan_dir),
            "--phase",
            "phase-1-stop-release-blockers",
            "--output-dir",
            str(output_dir),
            "--execute-safe-commands",
            "--workspace",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ready: true" in captured.out
    execution = json.loads((output_dir / "repair-execution-results.json").read_text(encoding="utf-8"))
    assert execution["success"] is True
    assert execution["commands"][0]["returncode"] == 0
    assert execution["commands"][0]["blocked"] is False
    attempt = json.loads((output_dir / "repair-execute-attempt" / "repair-execute-attempt.json").read_text(encoding="utf-8"))
    assert attempt["status"] == "complete"
    updated = json.loads((output_dir / "updated-repair-plan" / "repair-plan.json").read_text(encoding="utf-8"))
    assert updated["tasks"][0]["status"] == "complete"


def test_cli_eval_repair_execute_fails_when_no_safe_commands_declared(monkeypatch, tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "repair-plan.json").write_text(
        json.dumps(
            {
                "tasks": [],
                "phase_status_summary": {"executable_phases": ["phase-1"]},
                "phases": [{"id": "phase-1", "status": "open", "blocked_by": [], "task_ids": []}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda actual: [])

    output_dir = tmp_path / "execute"
    exit_code = cli.main(
        [
            "eval",
            "repair-execute",
            "--plan-dir",
            str(plan_dir),
            "--phase",
            "phase-1",
            "--output-dir",
            str(output_dir),
            "--execute-safe-commands",
        ]
    )

    capsys.readouterr()
    execution = json.loads((output_dir / "repair-execution-results.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert execution["success"] is False
    assert "no executable safe commands declared for phase: phase-1" in execution["failures"]


def test_cli_eval_repair_execute_blocks_unsafe_declared_commands(monkeypatch, tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "repair-plan.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "repair-001",
                        "execution_commands": [["python", "-c", "print('unsafe')"]],
                    }
                ],
                "phase_status_summary": {"executable_phases": ["phase-1"]},
                "phases": [{"id": "phase-1", "status": "open", "blocked_by": [], "task_ids": ["repair-001"]}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda actual: [])

    output_dir = tmp_path / "execute"
    exit_code = cli.main(
        [
            "eval",
            "repair-execute",
            "--plan-dir",
            str(plan_dir),
            "--phase",
            "phase-1",
            "--output-dir",
            str(output_dir),
            "--execute-safe-commands",
        ]
    )

    capsys.readouterr()
    execution = json.loads((output_dir / "repair-execution-results.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert execution["commands"][0]["blocked"] is True
    assert "inline Python execution is not allowed" in execution["commands"][0]["stderr"]


def test_cli_eval_repair_execute_preflight_fails_blocked_phase_json(monkeypatch, tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "repair-plan.json").write_text(
        json.dumps(
            {
                "phase_status_summary": {"executable_phases": ["phase-0b-repair-suite-hygiene"]},
                "phases": [
                    {
                        "id": "phase-1-stop-release-blockers",
                        "status": "blocked",
                        "blocked_by": ["phase-0b-repair-suite-hygiene"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "verify_repair_plan_attestation", lambda actual: [])

    exit_code = cli.main(
        [
            "eval",
            "repair-execute",
            "--plan-dir",
            str(plan_dir),
            "--phase",
            "phase-1-stop-release-blockers",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"ready": false' in captured.out
    assert '"phase_executable"' in captured.out
    assert "Required repair phase is not executable: phase-1-stop-release-blockers" in captured.out


def test_cli_eval_repair_execute_preflight_fails_attestation_before_ready(monkeypatch, tmp_path, capsys):
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "repair-plan.json").write_text(
        json.dumps({"phase_status_summary": {"executable_phases": ["phase-1"]}, "phases": [{"id": "phase-1"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        cli,
        "verify_repair_plan_attestation",
        lambda actual: ["repair-plan-attestation digest mismatch for repair-plan.json"],
    )

    exit_code = cli.main(["eval", "repair-execute", "--plan-dir", str(plan_dir), "--phase", "phase-1"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Ready: false" in captured.out
    assert "repair-plan-attestation digest mismatch for repair-plan.json" in captured.out


def test_cli_eval_verify_repair_preflight_prints_markdown_and_returns_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "verify_repair_execute_preflight_attestation", lambda preflight_dir: [])

    exit_code = cli.main(["eval", "verify-repair-preflight", "--preflight-dir", str(tmp_path / "preflight")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metis Repair Execute Preflight Verification" in captured.out
    assert "Artifact: repair_execute_preflight" in captured.out
    assert "Verified: true" in captured.out


def test_cli_eval_verify_repair_preflight_prints_json_and_returns_failure(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "verify_repair_execute_preflight_attestation",
        lambda preflight_dir: [
            "repair-execute-preflight-attestation.json digest mismatch for repair-execute-preflight.json"
        ],
    )

    exit_code = cli.main(
        ["eval", "verify-repair-preflight", "--preflight-dir", str(tmp_path / "preflight"), "--json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"artifact": "repair_execute_preflight"' in captured.out
    assert '"verified": false' in captured.out
    assert "repair-execute-preflight-attestation.json digest mismatch for repair-execute-preflight.json" in captured.out


def test_cli_eval_stubs_writes_outputs(monkeypatch, tmp_path, capsys):
    repair_tasks = {"profile": "release", "tasks": []}
    stubs = {"profile": "release", "stub_count": 1, "stubs": [{"id": "targeted-repair-001"}]}
    calls = []

    monkeypatch.setattr(cli, "load_repair_tasks", lambda path: calls.append({"load": path}) or repair_tasks)
    monkeypatch.setattr(cli, "build_eval_stubs_from_repair_tasks", lambda actual: calls.append({"build": actual}) or stubs)
    monkeypatch.setattr(cli, "write_eval_stubs", lambda actual, output_dir: calls.append({"write": actual, "output_dir": output_dir}))

    exit_code = cli.main(
        [
            "eval",
            "eval-stubs",
            "--repair-tasks",
            str(tmp_path / "repair-tasks.json"),
            "--output-dir",
            str(tmp_path / "stubs"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        {"load": str(tmp_path / "repair-tasks.json")},
        {"build": repair_tasks},
        {"write": stubs, "output_dir": str(tmp_path / "stubs")},
    ]
    assert "Metis Targeted Eval Stubs" in captured.out
    assert "targeted-repair-001" in captured.out


def test_cli_eval_stubs_can_print_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "load_repair_tasks", lambda path: {"tasks": []})
    monkeypatch.setattr(
        cli,
        "build_eval_stubs_from_repair_tasks",
        lambda repair_tasks: {"profile": "release", "stub_count": 0, "stubs": []},
    )

    exit_code = cli.main(["eval", "eval-stubs", "--repair-tasks", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"stub_count": 0' in captured.out


def test_cli_eval_materialize_stubs_writes_outputs(monkeypatch, tmp_path, capsys):
    suite = {
        "suite": "targeted-repair-regression",
        "task_count": 1,
        "tasks": [{"task_id": "targeted-repair-001", "task_spec": {"id": "targeted-repair-001", "prompt": "run"}}],
    }
    calls = []

    monkeypatch.setattr(cli, "materialize_eval_suite", lambda path: calls.append({"materialize": path}) or suite)
    monkeypatch.setattr(
        cli,
        "write_materialized_eval_suite",
        lambda actual, output_dir: calls.append({"write": actual, "output_dir": output_dir}),
    )

    exit_code = cli.main(
        [
            "eval",
            "materialize-stubs",
            "--stubs",
            str(tmp_path / "targeted-eval-stubs.json"),
            "--output-dir",
            str(tmp_path / "suite"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        {"materialize": str(tmp_path / "targeted-eval-stubs.json")},
        {"write": suite, "output_dir": str(tmp_path / "suite")},
    ]
    assert "Metis Materialized Targeted Eval Suite" in captured.out
    assert "targeted-repair-001" in captured.out


def test_cli_eval_materialize_stubs_can_print_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "materialize_eval_suite",
        lambda path: {"suite": "targeted-repair-regression", "task_count": 0, "tasks": []},
    )

    exit_code = cli.main(["eval", "materialize-stubs", "--stubs", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"suite": "targeted-repair-regression"' in captured.out


def test_cli_eval_run_suite_refuses_to_fake_without_endpoint(monkeypatch, capsys):
    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: False)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite: True)
    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite, **context: {"valid": True, "errors": []})

    exit_code = cli.main(["eval", "run-suite", "--suite", "suite.json"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "requires METIS_BASE_URL, METIS_API_KEY, and METIS_MODEL" in captured.out
    assert "no model result was faked" in captured.out


def test_cli_eval_run_suite_allows_deterministic_fixture_without_endpoint(monkeypatch, tmp_path, capsys):
    report_dir = tmp_path / "docs" / "evals" / "runs" / "artifact"
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="artifact-verification-repair-001",
                success=True,
                status="verified",
                turns_used=0,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ],
        metadata={"suite": "targeted-repair-regression", "task_count": 1},
    )
    calls = []

    async def fake_run(*, suite_path, workspace, profile):
        calls.append({"run": suite_path})
        return suite

    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: calls.append({"env": True}) or False)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite_path: False)
    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": {"run_attestation_verifies"}})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(cli, "run_generic_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_generic_eval_pre_run_contract", lambda **kwargs: report_dir)
    monkeypatch.setattr(cli, "write_generic_eval_suite_reports", lambda actual, *, output_root, run_name: report_dir)

    exit_code = cli.main(["eval", "run-suite", "--suite", str(tmp_path / "suite.json")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert {"env": True} not in calls
    assert {"run": str(tmp_path / "suite.json")} in calls
    assert "Generic eval suite complete: success_rate=100.00%" in captured.out


def test_cli_eval_run_suite_refuses_targeted_suite_when_attestation_fails(monkeypatch, tmp_path, capsys):
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "targeted-eval-suite.json").write_text('{"suite":"targeted-repair-regression"}', encoding="utf-8")
    (suite_dir / "targeted-eval-suite.md").write_text("# suite", encoding="utf-8")

    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(
        cli,
        "verify_targeted_eval_suite_attestation",
        lambda suite_dir: ["targeted-eval-suite-attestation.json missing from repair eval artifact directory"],
    )
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite_path: False)

    exit_code = cli.main(["eval", "run-suite", "--suite", str(suite_dir)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "targeted suite attestation failed" in captured.out
    assert "targeted-eval-suite-attestation.json missing" in captured.out


def test_cli_eval_run_suite_verifies_targeted_suite_attestation_before_running(monkeypatch, tmp_path, capsys):
    suite_dir = tmp_path / "suite"
    suite_dir.mkdir()
    (suite_dir / "targeted-eval-suite.json").write_text('{"suite":"targeted-repair-regression"}', encoding="utf-8")
    (suite_dir / "targeted-eval-suite.md").write_text("# suite", encoding="utf-8")
    report_dir = tmp_path / "docs" / "evals" / "runs" / "targeted"
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=True,
                status="verified",
                turns_used=0,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ],
        metadata={"suite": "targeted-repair-regression", "task_count": 1},
    )
    calls = []

    async def fake_run(*, suite_path, workspace, profile):
        calls.append({"run": suite_path})
        return suite

    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(cli, "verify_targeted_eval_suite_attestation", lambda actual: calls.append({"verify": str(actual)}) or [])
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite_path: False)
    monkeypatch.setattr(cli, "run_generic_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_generic_eval_pre_run_contract", lambda **kwargs: report_dir)
    monkeypatch.setattr(cli, "write_generic_eval_suite_reports", lambda actual, *, output_root, run_name: report_dir)

    exit_code = cli.main(["eval", "run-suite", "--suite", str(suite_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls[0] == {"verify": str(suite_dir)}
    assert {"run": str(suite_dir)} in calls
    assert "Generic eval suite complete: success_rate=100.00%" in captured.out


def test_cli_eval_run_suite_validates_before_endpoint_check(monkeypatch, capsys):
    validation = {
        "path": "bad.json",
        "suite": "bad",
        "schema_version": "1",
        "task_count": 0,
        "valid": False,
        "error_count": 1,
        "warning_count": 0,
        "errors": [{"path": "tasks", "code": "empty", "message": "tasks must contain at least one eval task."}],
        "warnings": [],
    }
    env_calls = []

    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": {"read_file"}, "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite, **context: validation)
    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: env_calls.append("env") or False)

    exit_code = cli.main(["eval", "run-suite", "--suite", "bad.json"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert env_calls == []
    assert "Valid: False" in captured.out
    assert "suite validation failed" in captured.out


def test_cli_eval_run_suite_writes_reports_when_endpoint_configured(monkeypatch, tmp_path, capsys):
    report_dir = tmp_path / "docs" / "evals" / "runs" / "targeted"
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ],
        metadata={"suite": "targeted-repair-regression", "task_count": 1},
    )
    calls = []

    async def fake_run(*, suite_path, workspace, profile):
        calls.append({"suite_path": suite_path, "workspace": workspace, "profile": profile})
        return suite

    def fake_write(actual_suite, *, output_root, run_name):
        calls.append({"suite": actual_suite, "output_root": output_root, "run_name": run_name})
        return report_dir

    def fake_pre_run(**kwargs):
        calls.append({"pre_run": kwargs})
        return report_dir

    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: True)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite: True)
    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(cli, "run_generic_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_generic_eval_pre_run_contract", fake_pre_run)
    monkeypatch.setattr(cli, "write_generic_eval_suite_reports", fake_write)

    exit_code = cli.main(
        [
            "eval",
            "run-suite",
            "--suite",
            str(tmp_path / "targeted-eval-suite.json"),
            "--workspace",
            str(tmp_path / "workspace"),
            "--output-root",
            str(tmp_path),
            "--run-name",
            "targeted",
            "--profile",
            "small_strict",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        {
            "pre_run": {
                "suite_path": str(tmp_path / "targeted-eval-suite.json"),
                "workspace": str(tmp_path / "workspace"),
                "output_root": str(tmp_path),
                "profile": "small_strict",
                "run_name": "targeted",
                "requested_run_name": "targeted",
            }
        },
        {
            "suite_path": str(tmp_path / "targeted-eval-suite.json"),
            "workspace": str(tmp_path / "workspace"),
            "profile": "small_strict",
        },
        {"suite": suite, "output_root": str(tmp_path), "run_name": "targeted"},
    ]
    assert "success_rate=100.00%" in captured.out
    assert str(report_dir) in captured.out


def test_cli_eval_run_suite_can_run_gate(monkeypatch, tmp_path, capsys):
    report_dir = tmp_path / "docs" / "evals" / "runs" / "targeted"
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ]
    )
    gate = {
        "passed": True,
        "run": {"run_name": "targeted", "run_dir": str(report_dir), "success_rate": 1.0},
        "thresholds": {},
        "aggregates": {},
        "failed_tasks": [],
        "failures": [],
    }
    calls = []

    async def fake_run(*, suite_path, workspace, profile):
        return suite

    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: True)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite: True)
    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(cli, "run_generic_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_generic_eval_pre_run_contract", lambda **kwargs: report_dir)
    monkeypatch.setattr(cli, "write_generic_eval_suite_reports", lambda actual, *, output_root, run_name: report_dir)
    monkeypatch.setattr(cli, "evaluate_eval_run_gate", lambda run: calls.append({"gate": run}) or gate)
    monkeypatch.setattr(cli, "write_eval_gate_report", lambda actual, output_dir: calls.append({"write_gate": output_dir}))

    exit_code = cli.main(["eval", "run-suite", "--suite", str(tmp_path), "--gate"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [{"gate": report_dir}, {"write_gate": str(report_dir / "gate")}]
    assert "Passed: True" in captured.out


def test_cli_eval_run_suite_gate_refuses_unversioned_suite(monkeypatch, tmp_path, capsys):
    validation = {
        "path": str(tmp_path),
        "suite": "legacy",
        "schema_version": "unversioned",
        "supported_schema_versions": ["1"],
        "task_count": 1,
        "valid": True,
        "error_count": 0,
        "warning_count": 1,
        "errors": [],
        "warnings": [
            {
                "path": "schema_version",
                "code": "missing",
                "message": "schema_version is missing; defaulting to unversioned.",
            }
        ],
    }
    calls = []

    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: validation)
    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: calls.append("env") or True)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite: True)

    exit_code = cli.main(["eval", "run-suite", "--suite", str(tmp_path), "--gate"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls == []
    assert "Schema version: unversioned" in captured.out
    assert "release gate requires a declared supported schema_version" in captured.out


def test_cli_eval_run_suite_can_compare_explicit_baseline(monkeypatch, tmp_path, capsys):
    report_dir = tmp_path / "docs" / "evals" / "runs" / "current"
    baseline_dir = tmp_path / "docs" / "evals" / "runs" / "baseline"
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ]
    )
    comparison = {
        "has_regression": False,
        "baseline": {"run_name": "baseline", "run_dir": str(baseline_dir)},
        "current": {"run_name": "current", "run_dir": str(report_dir)},
        "success_rate_delta": 0.0,
        "newly_failed_tasks": [],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    calls = []

    async def fake_run(*, suite_path, workspace, profile):
        return suite

    def fake_compare(*, baseline_dir, current_dir, profile):
        calls.append({"baseline_dir": baseline_dir, "current_dir": current_dir, "profile": profile})
        return comparison

    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: True)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite: True)
    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(cli, "run_generic_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_generic_eval_pre_run_contract", lambda **kwargs: report_dir)
    monkeypatch.setattr(cli, "write_generic_eval_suite_reports", lambda actual, *, output_root, run_name: report_dir)
    monkeypatch.setattr(cli, "compare_eval_runs", fake_compare)
    monkeypatch.setattr(cli, "write_eval_run_comparison", lambda actual, output_dir: calls.append({"output_dir": output_dir}))

    exit_code = cli.main(
        [
            "eval",
            "run-suite",
            "--suite",
            str(tmp_path / "targeted-eval-suite.json"),
            "--compare-baseline",
            str(baseline_dir),
            "--compare-profile",
            "strict",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        {"baseline_dir": str(baseline_dir), "current_dir": report_dir, "profile": "strict"},
        {"output_dir": str(report_dir / "comparison")},
    ]
    assert "Has regression: False" in captured.out
    assert "Comparison written to:" in captured.out


def test_cli_eval_run_suite_compare_latest_uses_previous_pointer(monkeypatch, tmp_path, capsys):
    runs_root = tmp_path / "docs" / "evals" / "runs"
    previous_dir = runs_root / "previous"
    current_dir = runs_root / "current"
    runs_root.mkdir(parents=True)
    (runs_root / "latest.json").write_text(
        '{"latest_run_dir": "' + str(previous_dir).replace("\\", "\\\\") + '"}',
        encoding="utf-8",
    )
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ]
    )
    comparison = {
        "has_regression": True,
        "baseline": {"run_name": "previous", "run_dir": str(previous_dir)},
        "current": {"run_name": "current", "run_dir": str(current_dir)},
        "success_rate_delta": -1.0,
        "newly_failed_tasks": ["targeted-repair-001"],
        "recovered_tasks": [],
        "still_failed_tasks": [],
        "new_tasks": [],
        "removed_tasks": [],
        "regressed_metrics": [],
    }
    calls = []

    async def fake_run(*, suite_path, workspace, profile):
        return suite

    def fake_compare(*, baseline_dir, current_dir, profile):
        calls.append({"baseline_dir": baseline_dir, "current_dir": current_dir, "profile": profile})
        return comparison

    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: True)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite: True)
    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(cli, "run_generic_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_generic_eval_pre_run_contract", lambda **kwargs: current_dir)
    monkeypatch.setattr(cli, "write_generic_eval_suite_reports", lambda actual, *, output_root, run_name: current_dir)
    monkeypatch.setattr(cli, "compare_eval_runs", fake_compare)
    monkeypatch.setattr(cli, "write_eval_run_comparison", lambda actual, output_dir: None)

    exit_code = cli.main(["eval", "run-suite", "--suite", str(tmp_path), "--output-root", str(tmp_path), "--compare-latest"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls == [{"baseline_dir": str(previous_dir), "current_dir": current_dir, "profile": "release"}]
    assert "Has regression: True" in captured.out


def test_cli_eval_run_suite_compare_latest_fails_without_previous_pointer(monkeypatch, tmp_path, capsys):
    suite = EvalSuiteResult(
        [
            EvalResult(
                task_id="targeted-repair-001",
                success=True,
                status="final",
                turns_used=1,
                tool_calls=0,
                latency_seconds=0.01,
            )
        ]
    )

    async def fake_run(*, suite_path, workspace, profile):
        return suite

    monkeypatch.setattr(cli, "generic_eval_env_configured", lambda: True)
    monkeypatch.setattr(cli, "generic_eval_suite_requires_model_execution", lambda suite: True)
    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: {"available_tools": set(), "available_quality_gates": set()})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite_path, **context: {"valid": True, "errors": []})
    monkeypatch.setattr(cli, "run_generic_eval_suite", fake_run)
    monkeypatch.setattr(cli, "write_generic_eval_pre_run_contract", lambda **kwargs: tmp_path / "docs" / "evals" / "runs" / "current")
    monkeypatch.setattr(
        cli,
        "write_generic_eval_suite_reports",
        lambda actual, *, output_root, run_name: tmp_path / "docs" / "evals" / "runs" / "current",
    )

    exit_code = cli.main(["eval", "run-suite", "--suite", str(tmp_path), "--output-root", str(tmp_path), "--compare-latest"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Cannot compare latest" in captured.out


def test_cli_eval_validate_suite_writes_outputs(monkeypatch, tmp_path, capsys):
    validation = {
        "path": "suite.json",
        "suite": "suite",
        "schema_version": "1",
        "task_count": 1,
        "valid": True,
        "error_count": 0,
        "warning_count": 0,
        "errors": [],
        "warnings": [],
    }
    calls = []

    monkeypatch.setattr(cli, "generic_eval_validation_context", lambda workspace: calls.append({"workspace": workspace}) or {"available_tools": {"read_file"}, "available_quality_gates": {"artifact_exists"}})
    monkeypatch.setattr(cli, "validate_eval_suite", lambda suite, **context: calls.append({"suite": suite, "context": context}) or validation)
    monkeypatch.setattr(cli, "write_eval_suite_validation", lambda report, output_dir: calls.append({"report": report, "output_dir": output_dir}))

    exit_code = cli.main(
        [
            "eval",
            "validate-suite",
            "--suite",
            str(tmp_path / "targeted-eval-suite.json"),
            "--workspace",
            str(tmp_path / "workspace"),
            "--output-dir",
            str(tmp_path / "validation"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        {"workspace": str(tmp_path / "workspace")},
        {
            "suite": str(tmp_path / "targeted-eval-suite.json"),
            "context": {"available_tools": {"read_file"}, "available_quality_gates": {"artifact_exists"}},
        },
        {"report": validation, "output_dir": str(tmp_path / "validation")},
    ]
    assert "Metis Eval Suite Validation" in captured.out
    assert "Valid: True" in captured.out


def test_cli_eval_validate_suite_can_print_json_and_return_nonzero(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "validate_eval_suite",
        lambda suite, **context: {
            "path": str(tmp_path),
            "suite": "",
            "schema_version": "unversioned",
            "task_count": 0,
            "valid": False,
            "error_count": 1,
            "warning_count": 0,
            "errors": [{"path": "tasks", "code": "empty", "message": "tasks must contain at least one eval task."}],
            "warnings": [],
        },
    )

    exit_code = cli.main(["eval", "validate-suite", "--suite", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert '"valid": false' in captured.out


def test_cli_eval_list_tools_prints_markdown(monkeypatch, tmp_path, capsys):
    inventory = {
        "workspace": str(tmp_path),
        "tool_count": 1,
        "tools": [
            {
                "name": "read_file",
                "description": "Read",
                "category": "files",
                "side_effect": "read",
                "requires_permission": False,
                "retry_policy": "default",
                "verification": None,
                "metadata": {},
                "parameters": {"type": "object"},
            }
        ],
    }
    calls = []

    monkeypatch.setattr(cli, "generic_eval_tool_inventory", lambda workspace: calls.append({"workspace": workspace}) or inventory)

    exit_code = cli.main(["eval", "list-tools", "--workspace", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [{"workspace": str(tmp_path)}]
    assert "Metis Eval Tool Inventory" in captured.out
    assert "read_file" in captured.out


def test_cli_eval_list_tools_can_print_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "generic_eval_tool_inventory", lambda workspace: {"workspace": workspace, "tool_count": 0, "tools": []})

    exit_code = cli.main(["eval", "list-tools", "--workspace", str(tmp_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"tool_count": 0' in captured.out


def test_cli_eval_list_quality_gates_prints_markdown(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "generic_eval_quality_gate_inventory",
        lambda: {
            "gate_count": 1,
            "quality_gates": [
                {
                    "name": "artifact_exists",
                    "description": "Artifacts must exist",
                    "failure_policy": "fail",
                    "metadata": {},
                }
            ],
        },
    )

    exit_code = cli.main(["eval", "list-quality-gates"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metis Eval Quality Gate Inventory" in captured.out
    assert "artifact_exists" in captured.out


def test_cli_eval_list_quality_gates_can_print_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "generic_eval_quality_gate_inventory", lambda: {"gate_count": 0, "quality_gates": []})

    exit_code = cli.main(["eval", "list-quality-gates", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"gate_count": 0' in captured.out


def test_cli_trace_show_renders_timeline(tmp_path, capsys):
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(
        '{"task_id":"t1","status":"blocked","success":false,"events":[{"event_type":"error","error":"bad"}]}',
        encoding="utf-8",
    )

    exit_code = cli.main(["trace", "show", "--timeline", str(timeline_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metis Trace Timeline" in captured.out
    assert "t1:000:error" in captured.out


def test_cli_trace_show_can_print_json(tmp_path, capsys):
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text('{"task_id":"t1","events":[{"event_type":"task.end"}]}', encoding="utf-8")

    exit_code = cli.main(["trace", "show", "--timeline", str(timeline_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"event_id": "t1:000:task.end"' in captured.out


def test_cli_eval_gate_returns_nonzero_when_gate_fails(monkeypatch, capsys):
    gate = {
        "passed": False,
        "run": {"run_name": "run", "run_dir": "run", "success_rate": 0.5},
        "thresholds": {},
        "aggregates": {},
        "failed_tasks": ["a"],
        "failures": ["success_rate 0.5000 < 1.0000"],
    }
    calls = []

    def fake_gate(run, **kwargs):
        calls.append({"run": run, **kwargs})
        return gate

    monkeypatch.setattr(cli, "evaluate_eval_run_gate", fake_gate)

    exit_code = cli.main(["eval", "gate", "--run", "run"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls[0]["run"] == "run"
    assert calls[0]["min_success_rate"] == 1.0
    assert calls[0]["min_schema_repair_hint_recovery_rate"] == 0.0
    assert calls[0]["max_schema_repair_hint_failures"] == 0
    assert calls[0]["max_failure_clusters"] == 0
    assert calls[0]["max_critical_remediations"] == 0
    assert calls[0]["require_suite_schema_evidence"] is True
    assert calls[0]["require_task_contract_evidence"] is True
    assert calls[0]["require_provenance_evidence"] is True
    assert calls[0]["require_pre_run_contract_evidence"] is True
    assert calls[0]["require_run_attestation_evidence"] is True
    assert "Passed: False" in captured.out


def test_cli_eval_gate_can_write_output_and_print_json(monkeypatch, tmp_path, capsys):
    gate = {
        "passed": True,
        "run": {"run_name": "run", "run_dir": "run", "success_rate": 1.0},
        "thresholds": {},
        "aggregates": {},
        "failed_tasks": [],
        "failures": [],
    }
    output_calls = []

    monkeypatch.setattr(cli, "evaluate_eval_run_gate", lambda run, **kwargs: gate)
    monkeypatch.setattr(cli, "write_eval_gate_report", lambda actual, output_dir: output_calls.append((actual, output_dir)))

    exit_code = cli.main(
        [
            "eval",
            "gate",
            "--run",
            "run",
            "--output-dir",
            str(tmp_path),
            "--json",
            "--min-success-rate",
            "0.95",
            "--max-schema-violations",
            "1",
            "--min-schema-repair-hint-recovery-rate",
            "0.8",
            "--max-schema-repair-hint-failures",
            "1",
            "--max-failure-clusters",
            "2",
            "--max-critical-remediations",
            "1",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_calls == [(gate, str(tmp_path))]
    assert '"passed": true' in captured.out
