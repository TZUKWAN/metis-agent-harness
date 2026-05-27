"""Tests for Swarm Coordinator task decomposition schemas."""

from __future__ import annotations

import pytest

from metis.swarm.schemas import TaskAssignment, TaskDecomposition


def test_task_assignment_defaults() -> None:
    t = TaskAssignment(task="write tests")
    assert t.agent_id is None
    assert t.agent_name == ""
    assert t.priority == 0
    assert t.capabilities_needed == []


def test_task_assignment_full() -> None:
    t = TaskAssignment(
        agent_id="agent-1",
        agent_name="Coder",
        task="implement auth",
        priority=5,
        capabilities_needed=["code", "security"],
    )
    assert t.agent_id == "agent-1"
    assert t.priority == 5


def test_task_decomposition_empty() -> None:
    td = TaskDecomposition()
    assert td.tasks == []
    assert td.dependencies == {}
    assert td.topological_sort() == []


def test_task_decomposition_simple() -> None:
    td = TaskDecomposition(
        tasks=[
            TaskAssignment(task="step A"),
            TaskAssignment(task="step B"),
        ],
    )
    order = td.topological_sort()
    assert order == [0, 1]


def test_task_decomposition_with_dependencies() -> None:
    td = TaskDecomposition(
        tasks=[
            TaskAssignment(task="prepare data"),
            TaskAssignment(task="analyze"),
            TaskAssignment(task="report"),
        ],
        dependencies={
            "1": [0],
            "2": [1],
        },
    )
    order = td.topological_sort()
    assert order.index(0) < order.index(1)
    assert order.index(1) < order.index(2)


def test_task_decomposition_parallel_tasks() -> None:
    td = TaskDecomposition(
        tasks=[
            TaskAssignment(task="A"),
            TaskAssignment(task="B"),
            TaskAssignment(task="C"),
        ],
        dependencies={
            "2": [0, 1],
        },
    )
    order = td.topological_sort()
    assert order.index(2) > order.index(0)
    assert order.index(2) > order.index(1)
    # A and B can be in any order since they have no deps
    assert {order[0], order[1]} == {0, 1}


def test_task_decomposition_cycle_detection() -> None:
    td = TaskDecomposition(
        tasks=[
            TaskAssignment(task="A"),
            TaskAssignment(task="B"),
        ],
        dependencies={
            "0": [1],
            "1": [0],
        },
    )
    with pytest.raises(ValueError, match="Cycle"):
        td.validate_no_cycles()
    with pytest.raises(ValueError, match="Cycle"):
        td.topological_sort()


def test_task_decomposition_self_dependency() -> None:
    with pytest.raises(ValueError, match="cannot depend on itself"):
        TaskDecomposition(
            tasks=[TaskAssignment(task="A")],
            dependencies={"0": [0]},
        )


def test_task_decomposition_invalid_index() -> None:
    with pytest.raises(ValueError, match="out of range"):
        TaskDecomposition(
            tasks=[TaskAssignment(task="A")],
            dependencies={"0": [5]},
        )
