import pytest

from metis.prompts.assembler import PromptAssembler, PromptParts
from metis.runtime.strict_output import STRICT_OUTPUT_INSTRUCTIONS, StrictOutputError, StrictOutputParser


def test_prompt_assembler_injects_strict_output_contract():
    messages = PromptAssembler().build(PromptParts(user_message="run", strict_output=True))

    assert STRICT_OUTPUT_INSTRUCTIONS in messages[0]["content"]


def test_strict_output_parser_accepts_valid_contract():
    parsed = StrictOutputParser().parse(
        '{"status":"done","summary":"ok","evidence_refs":["e1"],"artifact_refs":[],"next_action":""}'
    )

    assert parsed.status == "done"
    assert parsed.evidence_refs == ["e1"]


def test_strict_output_parser_rejects_non_json():
    with pytest.raises(StrictOutputError):
        StrictOutputParser().parse("done")
