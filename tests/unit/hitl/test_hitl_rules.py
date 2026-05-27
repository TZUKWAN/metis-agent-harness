"""Tests for HITL approval rules."""

from metis.hitl.rules import ApprovalRule, default_approval_rules
from metis.tools.spec import ToolSpec


def test_rule_matches_tool_name_exact():
    rule = ApprovalRule(name="test", tool_names=["read_file", "write_file"])

    assert rule.matches("read_file", {}, None) is True
    assert rule.matches("delete_file", {}, None) is False


def test_rule_matches_permission_level():
    rule = ApprovalRule(name="test", permission_levels=["shell_dangerous"])
    spec = ToolSpec("run_cmd", "Run", {"type": "object"}, handler=lambda a, c: "", permission_level="shell_dangerous")

    assert rule.matches("run_cmd", {}, spec) is True
    assert rule.matches("read_file", {}, ToolSpec("read_file", "Read", {"type": "object"}, handler=lambda a, c: "")) is False


def test_rule_matches_side_effect():
    rule = ApprovalRule(name="test", side_effects=["destructive"])
    spec = ToolSpec("delete", "Delete", {"type": "object"}, handler=lambda a, c: "", side_effect="destructive")

    assert rule.matches("delete", {}, spec) is True
    assert rule.matches("read", {}, ToolSpec("read", "Read", {"type": "object"}, handler=lambda a, c: "", side_effect="read")) is False


def test_rule_matches_name_pattern():
    rule = ApprovalRule(name="test", name_patterns=[r"delete_.*", r"remove_.*"])

    assert rule.matches("delete_file", {}, None) is True
    assert rule.matches("remove_dir", {}, None) is True
    assert rule.matches("read_file", {}, None) is False


def test_rule_with_custom_matcher():
    rule = ApprovalRule(name="test", matcher=lambda tool, args, spec: "dangerous" in tool)

    assert rule.matches("dangerous_op", {}, None) is True
    assert rule.matches("safe_op", {}, None) is False


def test_default_rules_cover_destructive():
    rules = default_approval_rules()
    destructive_spec = ToolSpec("del", "Del", {"type": "object"}, handler=lambda a, c: "", side_effect="destructive")

    assert any(rule.matches("del", {}, destructive_spec) for rule in rules)


def test_default_rules_cover_credential_access():
    rules = default_approval_rules()
    cred_spec = ToolSpec("get_password", "Get", {"type": "object"}, handler=lambda a, c: "", permission_level="credential_access")

    assert any(rule.matches("get_password", {}, cred_spec) for rule in rules)


def test_default_rules_cover_network():
    rules = default_approval_rules()
    net_spec = ToolSpec("fetch", "Fetch", {"type": "object"}, handler=lambda a, c: "", side_effect="network")

    assert any(rule.matches("fetch", {}, net_spec) for rule in rules)
