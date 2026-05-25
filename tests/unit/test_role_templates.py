from metis.swarm.roles import RoleTemplateBank


def test_role_template_bank_returns_builtin_roles():
    bank = RoleTemplateBank()

    assert bank.get("explorer").allowed_tools == ["read_file", "run_shell"]
    assert "write_file" in bank.get("implementer").allowed_tools
    assert {role.role_id for role in bank.list_roles()} >= {"planner", "auditor", "synthesizer"}
