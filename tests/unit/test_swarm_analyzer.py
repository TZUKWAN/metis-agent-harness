from metis.swarm.analyzer import SwarmAnalyzer


def test_swarm_analyzer_keeps_simple_task_single_agent():
    decision = SwarmAnalyzer().analyze("读一个文件")

    assert decision.enabled is False


def test_swarm_analyzer_triggers_for_complex_audited_task():
    decision = SwarmAnalyzer().analyze("复杂多模块任务，需要审核团队和全量测试")

    assert decision.enabled is True
    assert "auditor" in decision.recommended_roles
