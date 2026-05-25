"""Parser chain with best-effort fallback."""

from __future__ import annotations

from typing import Any

from metis.providers.parsers.base import ToolCallParser
from metis.providers.parsers.hermes_xml import HermesXMLParser
from metis.providers.parsers.json_block import JsonBlockParser
from metis.runtime.errors import ParserError
from metis.runtime.response import ToolCall


class ParserChain(ToolCallParser):
    def __init__(self, parsers: list[ToolCallParser] | None = None) -> None:
        self.parsers = parsers or [HermesXMLParser(), JsonBlockParser()]

    def parse(self, raw: Any) -> list[ToolCall]:
        errors: list[str] = []
        for parser in self.parsers:
            try:
                calls = parser.parse(raw)
                if calls:
                    return calls
            except Exception as exc:
                errors.append(f"{type(parser).__name__}: {type(exc).__name__}: {exc}")
        if errors:
            raise ParserError("; ".join(errors))
        return []
