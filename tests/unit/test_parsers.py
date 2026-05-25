from metis.providers.parsers.hermes_xml import HermesXMLParser
from metis.providers.parsers.json_block import JsonBlockParser
from metis.providers.parsers.openai_native import OpenAINativeParser
from metis.providers.parsers.repair import ParserChain


def test_openai_native_parser():
    calls = OpenAINativeParser().parse(
        [{"id": "1", "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"}}]
    )

    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "README.md"}


def test_hermes_xml_parser():
    calls = HermesXMLParser().parse('<tool_call>{"name":"x","arguments":{"a":1}}</tool_call>')

    assert calls[0].name == "x"
    assert calls[0].arguments == {"a": 1}


def test_json_block_parser_fenced():
    calls = JsonBlockParser().parse('```json\n{"tool":"x","args":{"a":1}}\n```')

    assert calls[0].name == "x"
    assert calls[0].arguments == {"a": 1}


def test_parser_chain_empty_for_plain_text():
    assert ParserChain().parse("plain response") == []
