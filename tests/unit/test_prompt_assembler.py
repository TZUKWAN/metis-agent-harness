from metis.prompts.assembler import PromptAssembler, PromptLayer, PromptParts, PromptStack


def test_prompt_assembler_fences_context():
    messages = PromptAssembler().build(
        PromptParts(
            user_message="continue",
            task_contract="contract",
            memory_context="user prefers tests",
            workspace_context="README exists",
            recent_messages=[{"role": "assistant", "content": "prior"}],
            tool_policy="only read_file",
        )
    )

    assert messages[0]["role"] == "system"
    assert "contract" in messages[0]["content"]
    assert "<memory-context>" in messages[0]["content"]
    assert "not a new user instruction" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "continue"}


def test_prompt_stack_is_ordered_and_hashable():
    stack = PromptStack(
        [
            PromptLayer("base", "base rules", "test"),
            PromptLayer("disabled", "hidden", "test", enabled=False),
            PromptLayer("task", "do work", "test"),
        ]
    )

    content = stack.to_system_content()
    assert "base rules" in content
    assert "do work" in content
    assert "hidden" not in content
    assert stack.stack_hash() == PromptStack(
        [
            PromptLayer("base", "base rules", "test"),
            PromptLayer("task", "do work", "test"),
        ]
    ).stack_hash()


def test_prompt_stack_hash_changes_with_content():
    first = PromptStack([PromptLayer("base", "a", "test")])
    second = PromptStack([PromptLayer("base", "b", "test")])

    assert first.stack_hash() != second.stack_hash()
