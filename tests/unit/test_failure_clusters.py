import json

from metis.evals.failures import (
    build_remediation_backlog,
    cluster_failure_artifacts,
    failure_clusters_to_markdown,
    remediation_backlog_to_markdown,
    write_failure_clusters,
)


def write_failure(failures_dir, name, payload):
    path = failures_dir / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cluster_failure_artifacts_groups_by_failure_signals(tmp_path):
    failures_dir = tmp_path / "failures"
    failures_dir.mkdir()
    schema_path = write_failure(
        failures_dir,
        "schema.json",
        {
            "task_id": "schema-task",
            "status": "blocked",
            "metrics": {"schema_violations": 1, "trajectory_failures": 1},
            "tool_failure_types": {"schema_validation_failed": 1},
            "failure_shape_keys": {"write_file schema_validation_failed": 1},
            "schema_repair_hint_types_seen": {"add_required_property": 1},
            "schema_repair_hint_type_failures": {"add_required_property": 1},
            "task_spec_hashes": {"task_spec_hash": "abc"},
            "run_metadata": {"suite": "unit", "model": "fake-9b", "profile": "small"},
            "tool_result_excerpts": [
                {
                    "tool_name": "write_file",
                    "status": "blocked",
                    "metadata": {
                        "failure_type": "schema_validation_failed",
                        "schema_errors": ["$.path: missing required property"],
                        "schema_repair_hint_types": ["add_required_property"],
                        "schema_repair_hint_details": [
                            {
                                "hint_type": "add_required_property",
                                "schema_path": "$.path",
                                "schema_keyword": "required",
                                "schema_error": "$.path: missing required property",
                                "hint_text": "Add the required argument $.path.",
                            }
                        ],
                    },
                }
            ],
            "errors": ["Tool schema violation"],
        },
    )
    retry_path = write_failure(
        failures_dir,
        "retry.json",
        {
            "task_id": "retry-task",
            "status": "blocked",
            "metrics": {"retry_budget_exhaustions": 1, "pre_dispatch_blocks": 1},
            "tool_failure_types": {"retry_budget_exhausted": 1},
            "failure_shape_keys": {"python pytest": 2},
            "task_spec": {"required_tools": ["run_test"], "forbidden_tools": ["run_shell"]},
            "errors": ["Retry budget exhausted"],
        },
    )
    (failures_dir / "index.json").write_text(
        json.dumps(
            {
                "failure_count": 2,
                "artifacts": [
                    {"task_id": "schema-task", "path": str(schema_path), "errors": 1},
                    {"task_id": "retry-task", "path": str(retry_path), "errors": 1},
                ],
            }
        ),
        encoding="utf-8",
    )

    clusters = cluster_failure_artifacts(failures_dir)

    cluster_by_key = {cluster["cluster_key"]: cluster for cluster in clusters["clusters"]}
    assert clusters["failure_count"] == 2
    assert "tool_failure_type:schema_validation_failed" in cluster_by_key
    assert "failure_shape:write_file schema_validation_failed" in cluster_by_key
    assert "schema_failure" in cluster_by_key
    assert "schema_error:path_missing_required_property" in cluster_by_key
    assert "schema_repair_hint_type:add_required_property" in cluster_by_key
    assert "schema_repair_hint_failure_type:add_required_property" in cluster_by_key
    assert "schema_repair_hint_path:add_required_property:path" in cluster_by_key
    assert "retry_budget_failure" in cluster_by_key
    assert "tool_failure_type:retry_budget_exhausted" in cluster_by_key
    assert cluster_by_key["schema_failure"]["task_ids"] == ["schema-task"]
    assert "Tighten tool schema feedback" in cluster_by_key["schema_failure"]["remediation"]
    assert "targeted schema examples" in cluster_by_key["schema_error:path_missing_required_property"]["remediation"]
    assert "Improve failure lineage blocking" in cluster_by_key["retry_budget_failure"]["remediation"]
    assert "task_spec_hash=abc" in cluster_by_key["schema_failure"]["signals"]
    assert "run_model=fake-9b" in cluster_by_key["schema_failure"]["signals"]
    assert "schema_error=$.path: missing required property" in cluster_by_key["schema_failure"]["signals"]
    assert "schema_repair_hint_type=add_required_property" in cluster_by_key["schema_failure"]["signals"]
    assert "schema_repair_hint_failure_type:add_required_property=1" in cluster_by_key["schema_failure"]["signals"]
    assert "schema_repair_hint_detail=add_required_property@$.path:required" in cluster_by_key["schema_failure"]["signals"]
    backlog = build_remediation_backlog(clusters)
    item_by_cluster = {item["cluster_key"]: item for item in backlog["items"]}
    assert item_by_cluster["schema_failure"]["severity"] == "critical"
    assert item_by_cluster["schema_failure"]["owner_area"] == "tool-schema-and-repair"
    assert item_by_cluster["schema_error:path_missing_required_property"]["severity"] == "critical"
    assert item_by_cluster["schema_repair_hint_type:add_required_property"]["severity"] == "critical"
    assert item_by_cluster["schema_repair_hint_failure_type:add_required_property"]["severity"] == "critical"
    assert "schema-repair eval" in item_by_cluster["schema_failure"]["suggested_eval"]
    assert item_by_cluster["retry_budget_failure"]["severity"] == "critical"
    assert item_by_cluster["retry_budget_failure"]["owner_area"] == "runtime-lineage-and-recovery"


def test_cluster_failure_artifacts_uses_task_spec_constraint_signals(tmp_path):
    failures_dir = tmp_path / "failures"
    failures_dir.mkdir()
    failure_path = write_failure(
        failures_dir,
        "constraint.json",
        {
            "task_id": "constraint-task",
            "status": "final",
            "metrics": {"trajectory_failures": 3},
            "task_spec": {
                "required_tools": ["read_file"],
                "forbidden_tools": ["run_shell"],
                "required_tool_order": ["read_file", "write_file"],
                "required_tool_arguments": [{"tool": "read_file", "arguments": {"path": "README.md"}}],
            },
            "errors": [
                "Missing required tools: read_file",
                "Forbidden tools were called: run_shell",
                "Required tool order not satisfied: read_file -> write_file",
                "Required tool arguments not satisfied: {\"tool\":\"read_file\"}",
            ],
        },
    )
    (failures_dir / "index.json").write_text(
        json.dumps(
            {
                "failure_count": 1,
                "artifacts": [{"task_id": "constraint-task", "path": str(failure_path), "errors": 4}],
            }
        ),
        encoding="utf-8",
    )

    clusters = cluster_failure_artifacts(failures_dir)

    cluster_keys = {cluster["cluster_key"] for cluster in clusters["clusters"]}
    assert "task_constraint:required_tool_missing" in cluster_keys
    assert "task_constraint:forbidden_tool_used" in cluster_keys
    assert "task_constraint:tool_order_broken" in cluster_keys
    assert "task_constraint:tool_arguments_missing" in cluster_keys


def test_write_failure_clusters_outputs_json_and_markdown_for_empty_index(tmp_path):
    failures_dir = tmp_path / "failures"
    failures_dir.mkdir()
    (failures_dir / "index.json").write_text(json.dumps({"failure_count": 0, "artifacts": []}), encoding="utf-8")

    clusters = write_failure_clusters(failures_dir)
    markdown = failure_clusters_to_markdown(clusters)

    assert clusters == {"failure_count": 0, "cluster_count": 0, "clusters": []}
    assert (failures_dir / "clusters.json").exists()
    assert (failures_dir / "clusters.md").exists()
    assert (failures_dir / "remediation-backlog.json").exists()
    assert (failures_dir / "remediation-backlog.md").exists()
    assert "- None" in markdown
    backlog = build_remediation_backlog(clusters)
    backlog_md = remediation_backlog_to_markdown(backlog)
    assert backlog == {"failure_count": 0, "cluster_count": 0, "item_count": 0, "items": []}
    assert "- None" in backlog_md
