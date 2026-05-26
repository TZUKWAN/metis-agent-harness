"""Prompt injection scanner for external context.

NOTE: This is a shallow defense layer, not a complete solution.
It catches common injection patterns but cannot prevent all attacks.
Always combine with sandboxed tool execution and output validation.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


INJECTION_PATTERNS = (
    re.compile(r"ignore (all )?previous (instructions|rules|prompts|directives)", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"override (the )?(system|developer) instructions", re.I),
    re.compile(r"<(?:div|span|p|a)[^>]+style=['\"][^'\"]*(display\s*:\s*none|visibility\s*:\s*hidden)", re.I),
    re.compile(r"(exfiltrate|leak|send).{0,40}(secret|api key|token|credential)", re.I),
    re.compile(r"(forget|disregard|discard).{0,20}(previous|above|prior|all).{0,20}(instruction|rule|prompt|directive)", re.I),
    re.compile(r"(you are now|act as|pretend to be|role[ -]?play as).{0,30}(an? )?(unfiltered|unrestricted|uncensored|compliant|helpful)", re.I),
    re.compile(r"(do not|don't).{0,20}(follow|obey|respect|adhere to).{0,20}(your|the).{0,20}(rule|policy|guideline|restriction|boundary)", re.I),
    re.compile(r"(jailbreak|dan mode|developer mode|god mode|admin mode|root access)", re.I),
    re.compile(r"(output|print|show|reveal|display).{0,20}(your|the).{0,20}(system|initial|original|base).{0,20}(prompt|instruction|message)", re.I),
    re.compile(r"(ignoriere|vergiss|missachte).{0,30}(alle|vorherige|anstatt|anstelle)", re.I),
    re.compile(r"(ignorez|oubliez|ne respectez pas).{0,30}(toutes?|les|instructions?|consignes?)", re.I),
)

INVISIBLE_CHARS = {
    "​", "‌", "‍", "﻿",
    "­", "⁠", "⁡", "⁢", "⁣", "⁤",
    "᠎", "͏", "⁪", "⁫", "⁬", "⁭", "⁮", "⁯",
}

HOMOGLYPH_CATEGORIES = {" Cf"}  # Format characters


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
        normalized = unicodedata.normalize("NFKC", content)
        if normalized != content:
            reasons.append("unicode normalization difference")
        for char in content:
            if char in INVISIBLE_CHARS:
                reasons.append("invisible unicode")
                break
            cat = unicodedata.category(char)
            if cat == "Cf" and char not in INVISIBLE_CHARS:
                reasons.append("format character")
                break
        if reasons:
            return PromptInjectionScanResult(True, self.blocked_note, reasons)
        return PromptInjectionScanResult(False, content, [])
