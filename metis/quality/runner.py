"""Quality gate runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from metis.quality.gates import DEFAULT_GATES, GateResult, GateSpec


@dataclass(frozen=True)
class QualityRunResult:
    passed: bool
    results: list[GateResult] = field(default_factory=list)

    @property
    def failed_results(self) -> list[GateResult]:
        return [result for result in self.results if not result.passed]


class QualityGateRunner:
    def __init__(self, gates: dict[str, GateSpec] | None = None) -> None:
        self.gates = dict(DEFAULT_GATES)
        if gates:
            self.gates.update(gates)

    def register(self, spec: GateSpec) -> None:
        self.gates[spec.name] = spec

    def run(self, gate_names: list[str], context: dict[str, Any]) -> QualityRunResult:
        results: list[GateResult] = []
        for name in gate_names:
            spec = self.gates.get(name)
            if spec is None:
                results.append(GateResult(name, False, f"Unknown quality gate: {name}"))
                continue
            result = spec.handler(context)
            if result.name != name:
                result = GateResult(name, result.passed, result.message, result.metadata)
            results.append(result)
            if not result.passed and spec.failure_policy == "halt":
                break
        return QualityRunResult(passed=all(result.passed for result in results), results=results)
