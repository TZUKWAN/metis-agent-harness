from metis.context.compressor import SimpleContextCompressor
from metis.context.engine import ContextEngine
from metis.runtime.budgets import BudgetConfig


def test_context_compressor_keeps_system_and_recent_messages():
    messages = [{"role": "system", "content": "rules"}]
    messages += [{"role": "user", "content": f"message {i} " + ("x" * 80)} for i in range(12)]
    compressor = SimpleContextCompressor(max_summary_chars=300, keep_recent=3)

    result = compressor.compress(messages, max_chars=500)

    assert result.compressed is True
    assert result.messages[0]["content"] == "rules"
    assert result.messages[-1]["content"].startswith("message 11")
    assert any(message.get("metadata", {}).get("metis_context_summary") for message in result.messages)


def test_context_engine_compresses_above_budget():
    engine = ContextEngine(
        budget=BudgetConfig(model_context_tokens=100, context_threshold=0.5),
        compressor=SimpleContextCompressor(max_summary_chars=120, keep_recent=2),
        chars_per_token=1,
    )
    messages = [{"role": "user", "content": "x" * 40} for _ in range(10)]

    result = engine.build(messages)

    assert result.compressed is True
    assert result.final_chars <= result.original_chars
    assert result.max_chars == 50
