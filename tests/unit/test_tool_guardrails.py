from metis.runtime.response import ToolCall, ToolResult
from metis.tools.guardrails import ToolCallGuardrailController
from metis.tools.spec import ToolSpec


def test_guardrail_blocks_repeated_exact_failure():
    guardrails = ToolCallGuardrailController(max_exact_failures=2)
    call = ToolCall(name="bad", arguments={"x": 1})
    spec = ToolSpec("bad", "Bad", {"type": "object"}, lambda args, ctx: args)

    guardrails.after_call(call, spec, ToolResult("bad", "boom", status="error", error="boom"))
    guardrails.after_call(call, spec, ToolResult("bad", "boom", status="error", error="boom"))

    decision = guardrails.before_call(call, spec)

    assert decision.blocked is True
    assert "Repeated failed call" in decision.message
