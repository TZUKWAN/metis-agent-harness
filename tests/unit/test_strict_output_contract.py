import pytest

from metis.prompts.assembler import PromptAssembler, PromptParts
from metis.runtime.strict_output import (
    STRICT_OUTPUT_INSTRUCTIONS,
    STRICT_OUTPUT_INSTRUCTIONS_SOFT,
    StrictOutputError,
    StrictOutputParser,
)


def test_prompt_assembler_injects_strict_output_contract():
    messages = PromptAssembler().build(PromptParts(user_message="run", strict_output=True))

    assert STRICT_OUTPUT_INSTRUCTIONS in messages[0]["content"]


def test_prompt_assembler_uses_soft_instructions():
    messages = PromptAssembler().build(
        PromptParts(user_message="run", strict_output=True, strict_output_soft=True)
    )

    assert STRICT_OUTPUT_INSTRUCTIONS_SOFT in messages[0]["content"]


def test_strict_output_parser_accepts_valid_contract():
    parsed = StrictOutputParser().parse(
        '{"status":"done","summary":"ok","evidence_refs":["e1"],"artifact_refs":[],"next_action":""}'
    )

    assert parsed.status == "done"
    assert parsed.evidence_refs == ["e1"]


def test_strict_output_parser_rejects_non_json():
    with pytest.raises(StrictOutputError):
        StrictOutputParser().parse("done")


def test_parse_soft_wraps_plain_text():
    parsed = StrictOutputParser().parse_soft("I have read the file and completed the task.")

    assert parsed.status == "done"
    assert "read the file" in parsed.summary


def test_parse_soft_detects_blocked():
    parsed = StrictOutputParser().parse_soft("I cannot complete this task, blocked by permissions.")

    assert parsed.status == "blocked"


def test_parse_soft_detects_needs_more_work():
    parsed = StrictOutputParser().parse_soft("More work is needed to finish this.")

    assert parsed.status == "needs_more_work"


def test_parse_soft_passes_through_valid_json():
    parsed = StrictOutputParser().parse_soft(
        '{"status":"done","summary":"ok","evidence_refs":[],"artifact_refs":[],"next_action":""}'
    )

    assert parsed.status == "done"
    assert parsed.summary == "ok"


def test_parse_from_markdown_extracts_json_block():
    text = 'Here is my result:\n```json\n{"status":"done","summary":"ok","evidence_refs":[],"artifact_refs":[],"next_action":""}\n```\nDone!'

    parsed = StrictOutputParser().parse_from_markdown(text)

    assert parsed is not None
    assert parsed.status == "done"


def test_parse_from_markdown_extracts_bare_json():
    text = 'Result: {"status":"done","summary":"ok","evidence_refs":[],"artifact_refs":[],"next_action":""} end'

    parsed = StrictOutputParser().parse_from_markdown(text)

    assert parsed is not None
    assert parsed.status == "done"


def test_parse_from_markdown_returns_none_for_no_json():
    parsed = StrictOutputParser().parse_from_markdown("Just plain text, no JSON here.")

    assert parsed is None
