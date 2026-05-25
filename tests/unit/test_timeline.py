import json

from metis.telemetry.timeline import critical_event_id, load_timeline, timeline_event_ids, timeline_to_json, timeline_to_markdown


def test_load_timeline_normalizes_missing_event_ids(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text(
        json.dumps(
            {
                "task_id": "task-a",
                "status": "blocked",
                "success": False,
                "events": [
                    {"event_type": "task.start", "status": "started"},
                    {"event_type": "error", "status": "failed", "error": "bad tool"},
                ],
            }
        ),
        encoding="utf-8",
    )

    timeline = load_timeline(path)

    assert timeline["event_count"] == 2
    assert timeline["events"][0]["event_id"] == "task-a:000:task.start"
    assert timeline["events"][1]["event_id"] == "task-a:001:error"


def test_timeline_to_markdown_renders_event_table_and_payloads():
    timeline = {
        "task_id": "task-a",
        "status": "blocked",
        "success": False,
        "events": [
            {"index": 0, "event_id": "e0", "event_type": "task.start", "status": "started"},
            {
                "index": 1,
                "event_id": "e1",
                "event_type": "tool.result",
                "status": "blocked",
                "tool_name": "write_file",
                "metadata": {"failure_type": "schema_validation_failed"},
            },
        ],
    }

    markdown = timeline_to_markdown(timeline, include_payload=True)

    assert "Metis Trace Timeline" in markdown
    assert "| 1 | e1 | tool.result | blocked | write_file | failure_type=schema_validation_failed |" in markdown
    assert "## Event Payloads" in markdown


def test_timeline_to_markdown_renders_run_metadata_anchor():
    timeline = {
        "task_id": "task-a",
        "status": "blocked",
        "success": False,
        "run_metadata": {
            "pre_run_contract_path": "docs/evals/runs/current/pre-run-contract.json",
            "pre_run_contract_sha256": "contract-sha",
            "pre_run_provenance_hash": "pre-run-prov",
            "provenance_hash": "post-run-prov",
            "task_contract_hash": "task-contract",
            "suite_schema_sha256": "schema-sha",
        },
        "events": [{"index": 0, "event_id": "e0", "event_type": "task.start", "status": "started"}],
    }

    markdown = timeline_to_markdown(timeline)

    assert "Pre-run contract path: docs/evals/runs/current/pre-run-contract.json" in markdown
    assert "Pre-run contract sha256: contract-sha" in markdown
    assert "Pre-run provenance hash: pre-run-prov" in markdown
    assert "Provenance hash: post-run-prov" in markdown


def test_timeline_to_markdown_summarizes_schema_repair_hint_events():
    timeline = {
        "task_id": "task-a",
        "status": "blocked",
        "success": False,
        "events": [
            {
                "index": 0,
                "event_id": "e0",
                "event_type": "schema.repair_hint",
                "status": "emitted",
                "tool_name": "write_file",
                "attributes": {
                    "schema_repair_hint_types": ["add_required_property"],
                    "schema_repair_hints": ["Add the required argument $.path."],
                    "hint_count": 1,
                },
            },
        ],
    }

    markdown = timeline_to_markdown(timeline)

    assert (
        "| 0 | e0 | schema.repair_hint | emitted | write_file | "
        "schema_repair_hint_types=add_required_property |"
    ) in markdown


def test_timeline_to_json_outputs_normalized_json():
    payload = timeline_to_json({"task_id": "x", "events": [{"event_type": "task.end"}]})

    parsed = json.loads(payload)
    assert parsed["event_count"] == 1
    assert parsed["events"][0]["event_id"] == "x:000:task.end"


def test_timeline_event_ids_and_critical_event_prefer_failed_tool():
    timeline = {
        "task_id": "x",
        "events": [
            {"event_id": "e0", "event_type": "model.response", "status": "ok"},
            {
                "event_id": "e1",
                "event_type": "tool.result",
                "status": "blocked",
                "attributes": {"failed": True, "metadata": {"failure_type": "schema_validation_failed"}},
            },
            {"event_id": "e2", "event_type": "error", "status": "failed", "error": "schema"},
        ],
    }

    assert timeline_event_ids(timeline) == ["e0", "e1", "e2"]
    assert critical_event_id(timeline) == "e1"


def test_critical_event_prefers_schema_repair_hint_over_failed_tool():
    timeline = {
        "task_id": "x",
        "events": [
            {
                "event_id": "e1",
                "event_type": "tool.result",
                "status": "blocked",
                "attributes": {"failed": True, "metadata": {"failure_type": "schema_validation_failed"}},
            },
            {
                "event_id": "e2",
                "event_type": "schema.repair_hint",
                "status": "emitted",
                "attributes": {
                    "parent_event_id": "e1",
                    "schema_repair_hints": ["Add the required argument $.path."],
                    "schema_repair_hint_details": [{"hint_type": "add_required_property"}],
                },
            },
        ],
    }

    assert timeline_event_ids(timeline) == ["e1", "e2"]
    assert critical_event_id(timeline) == "e2"


def test_critical_event_prefers_finalization_error_when_no_tool_failed():
    timeline = {
        "task_id": "x",
        "events": [
            {"event_id": "e0", "event_type": "model.response", "status": "ok"},
            {
                "event_id": "e1",
                "event_type": "finalization.result",
                "status": "blocked",
                "attributes": {"error_count": 1},
            },
        ],
    }

    assert critical_event_id(timeline) == "e1"
