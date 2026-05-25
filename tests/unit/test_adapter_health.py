from pathlib import Path

from metis.adapters.aurora import AuroraAdapter
from metis.adapters.sophia import SophiaAdapter


def test_aurora_adapter_health_check():
    health = AuroraAdapter(Path(r"D:\LATEXTEST\aurora-agent")).health_check()

    assert health["name"] == "aurora"
    assert health["ok"] is True


def test_sophia_adapter_health_check():
    health = SophiaAdapter(Path(r"D:\LATEXTEST\sophia-agent")).health_check()

    assert health["name"] == "sophia"
    assert health["ok"] is True
