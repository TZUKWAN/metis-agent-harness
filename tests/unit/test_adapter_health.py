from metis.adapters.aurora import AuroraAdapter
from metis.adapters.sophia import SophiaAdapter


def test_aurora_adapter_health_check(tmp_path):
    project_root = tmp_path / "aurora-agent"
    project_root.mkdir()
    (project_root / "aurora").mkdir()
    (project_root / "aurora" / "agent.py").write_text("# aurora agent", encoding="utf-8")

    health = AuroraAdapter(project_root).health_check()

    assert health["name"] == "aurora"
    assert health["ok"] is True


def test_sophia_adapter_health_check(tmp_path):
    project_root = tmp_path / "sophia-agent"
    project_root.mkdir()
    (project_root / "sophia").mkdir()
    (project_root / "sophia" / "task_harness.py").write_text("# sophia harness", encoding="utf-8")

    health = SophiaAdapter(project_root).health_check()

    assert health["name"] == "sophia"
    assert health["ok"] is True
