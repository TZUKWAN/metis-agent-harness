from metis.swarm.decomposer import TaskDecomposer


def test_swarm_decomposer_creates_expected_roles():
    stages = TaskDecomposer().decompose("build harness")
    role_ids = [agent.role_id for stage in stages for agent in stage.agents]

    assert role_ids == ["explorer", "implementer", "verifier", "auditor"]
    assert stages[0].parallel is True
