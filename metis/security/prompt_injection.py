"""Prompt injection scanner for external context."""

from __future__ import annotations

import re
from dataclasses import dataclass


INJECTION_PATTERNS = (
    re.compile(r"ignore (all )?previous instructions", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"override (the )?(system|developer) instructions", re.I),
    re.compile(r"<(?:div|span|p|a)[^>]+style=['\"][^'\"]*(display\s*:\s*none|visibility\s*:\s*hidden)", re.I),
    re.compile(r"(exfiltrate|leak|send).{0,40}(secret|api key|token|credential)", re.I),
)
INVISIBLE_CHARS = {"\u200b", "\u200c", "\u200d", "\ufeff"}


@dataclass(frozen=True)
class PromptInjectionScanResult:
    blocked: bool
    content: str
    reasons: list[str]


class PromptInjectionScanner:
    blocked_note = "[BLOCKED: potential prompt injection content removed]"

    def scan(self, content: str) -> PromptInjectionScanResult:
        reasons: list[str] = []
        for pattern in INJECTION_PATTERNS:
            if pattern.search(content):
                reasons.append(pattern.pattern)
        if any(char in content for char in INVISIBLE_CHARS):
            reasons.append("invisible unicode")
        if reasons:
            return PromptInjectionScanResult(True, self.blocked_note, reasons)
        return PromptInjectionScanResult(False, content, [])
