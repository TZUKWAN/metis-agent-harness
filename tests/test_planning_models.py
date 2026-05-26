"""Tests for metis/planning/models.py."""

from metis.planning.models import Goal, Plan, Step


def test_goal_defaults():
    g = Goal(id="g1", session_id="s1", objective="build feature")
    assert g.status == "active"
    assert g.acceptance_criteria == []
    assert g.constraints == []


def test_plan_defaults():
    p = Plan(id="p1", goal_id="g1")
    assert p.version == 1
    assert p.status == "active"


def test_step_defaults():
    s = Step(
        id="s1", plan_id="p1", order_index=0,
        title="Read file", action="read_file",
        expected_output="contents", verification_method="check",
        done_condition="non-empty",
    )
    assert s.status == "pending"
    assert s.required_inputs == []
    assert s.allowed_tools == []
    assert s.evidence_refs == []

def test_goal_with_criteria():
    g = Goal(id="g2", session_id="s1", objective="test", acceptance_criteria=["a", "b"])
    assert len(g.acceptance_criteria) == 2

def test_step_with_tools():
    s = Step(
        id="s2", plan_id="p1", order_index=0,
        title="t", action="a", expected_output="x",
        verification_method="v", done_condition="d",
        allowed_tools=["read_file", "write_file"],
    )
    assert len(s.allowed_tools) == 2
