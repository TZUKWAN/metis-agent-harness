from metis.providers.parsers.hermes_xml import HermesXMLParser
from metis.providers.parsers.json_block import JsonBlockParser, _try_repair_json
from metis.providers.parsers.openai_native import OpenAINativeParser
from metis.providers.parsers.repair import ParserChain


def test_openai_native_parser():
    calls = OpenAINativeParser().parse(
        [{"id": "1", "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"}}]
    )

    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "README.md"}


def test_hermes_xml_parser():
    from metis.providers.parsers.hermes_xml import TOOL_CALL_RE
    p = TOOL_CALL_RE.pattern
    parts = p.split(r"\s")
    prefix = parts[0]
    suffix = parts[-1].replace("*", "")
    payload = '{"name":"x","arguments":{"a":1}}'
    text = prefix + payload + suffix
    calls = HermesXMLParser().parse(text)

    assert len(calls) == 1
    assert calls[0].name == "x"
    assert calls[0].arguments == {"a": 1}


def test_json_block_parser_fenced():
    calls = JsonBlockParser().parse('```json\n{"tool":"x","args":{"a":1}}\n```')

    assert calls[0].name == "x"
    assert calls[0].arguments == {"a": 1}


def test_parser_chain_empty_for_plain_text():
    assert ParserChain().parse("plain response") == []


def test_json_block_parser_trailing_comma_repair():
    calls = JsonBlockParser().parse('{"name":"read_file","arguments":{"path":"a.txt",}}')

    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "a.txt"}


def test_json_block_parser_control_chars_repair():
    text = '{"name":"write_file","arguments":{"path":"out.txt","content":"hello\nworld"}}'
    calls = JsonBlockParser().parse(text)

    assert len(calls) == 1
    assert calls[0].name == "write_file"


def test_json_block_pattern_fallback():
    text = 'I will call: "name": "read_file", "arguments": {"path": "test.py"}'
    calls = JsonBlockParser().parse(text)

    assert len(calls) == 1
    assert calls[0].name == "read_file"


def test_try_repair_json_trailing_comma():
    result = _try_repair_json('{"a": 1, "b": 2,}')
    assert result == {"a": 1, "b": 2}


def test_try_repair_json_trailing_comma_array():
    result = _try_repair_json('{"a": [1, 2,]}')
    assert result == {"a": [1, 2]}


def test_try_repair_json_invalid():
    result = _try_repair_json("not json at all")
    assert result is None


def test_json_block_parser_handles_bare_json():
    calls = JsonBlockParser().parse('{"name":"x","arguments":{"a":1}}')
    assert len(calls) == 1
    assert calls[0].name == "x"
