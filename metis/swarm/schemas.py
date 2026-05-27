"""Pydantic schemas for Swarm Coordinator task decomposition."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskAssignment(BaseModel):
    """A single task assigned to a worker agent."""

    agent_id: str | None = Field(
        default=None,
        description="Target agent ID. If None, coordinator will auto-match by capability.",
    )
    agent_name: str = Field(default="", description="Human-readable agent name or role")
    task: str = Field(..., description="Detailed task description for the worker")
    priority: int = Field(default=0, ge=0, le=10, description="Priority 0-10, higher first")
    capabilities_needed: list[str] = Field(
        default_factory=list,
        description="Required capabilities for this task (e.g. ['code', 'analysis'])",
    )


class TaskDecomposition(BaseModel):
    """Structured task decomposition output from the coordinator."""

    tasks: list[TaskAssignment] = Field(
        default_factory=list,
        description="List of task assignments",
    )
    dependencies: dict[str, list[str | int]] = Field(
        default_factory=dict,
        description="DAG: task index -> list of prerequisite task indices (0-based)",
    )
    reasoning: str = Field(
        default="",
        description="Coordinator's reasoning for the decomposition",
    )

    @field_validator("dependencies")
    @classmethod
    def _validate_dependencies(cls, v: dict[str, list[str | int]], info: Any) -> dict[str, list[str | int]]:
        """Validate that all dependency indices reference valid tasks."""
        tasks = info.data.get("tasks", []) if hasattr(info, "data") else []
        n = len(tasks)
        for task_idx_str, deps in v.items():
            try:
                task_idx = int(task_idx_str)
            except ValueError:
                raise ValueError(f"dependency key '{task_idx_str}' must be an integer")
            if not (0 <= task_idx < n):
                raise ValueError(f"dependency key {task_idx} out of range (0-{n - 1})")
            for dep in deps:
                dep_idx = int(dep) if isinstance(dep, str) else dep
                if not (0 <= dep_idx < n):
                    raise ValueError(f"dependency {dep_idx} for task {task_idx} out of range")
                if dep_idx == task_idx:
                    raise ValueError(f"task {task_idx} cannot depend on itself")
        return v

    def validate_no_cycles(self) -> None:
        """Detect cycles in the dependency graph. Raises ValueError if cycle found."""
        visited: set[int] = set()
        rec_stack: set[int] = set()

        def _has_cycle(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in self.dependencies.get(str(node), []):
                neighbor_idx = int(neighbor) if isinstance(neighbor, str) else neighbor
                if neighbor_idx not in visited:
                    if _has_cycle(neighbor_idx):
                        return True
                elif neighbor_idx in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for i in range(len(self.tasks)):
            if i not in visited:
                if _has_cycle(i):
                    raise ValueError("Cycle detected in task dependencies")

    def topological_sort(self) -> list[int]:
        """Return task indices in topological order (respecting dependencies).

        Raises ValueError if cycle detected.
        """
        self.validate_no_cycles()
        n = len(self.tasks)
        in_degree: dict[int, int] = {i: 0 for i in range(n)}
        adj: dict[int, list[int]] = {i: [] for i in range(n)}

        for task_idx_str, deps in self.dependencies.items():
            task_idx = int(task_idx_str)
            for dep in deps:
                dep_idx = int(dep) if isinstance(dep, str) else dep
                adj[dep_idx].append(task_idx)
                in_degree[task_idx] = in_degree.get(task_idx, 0) + 1

        queue = [i for i in range(n) if in_degree[i] == 0]
        result: list[int] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != n:
            raise ValueError("Cycle detected in task dependencies")
        return result
