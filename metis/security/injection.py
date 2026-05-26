"""Prompt injection detection with heuristic rules."""

from __future__ import annotations

import re
from dataclasses import dataclass


PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:prior\s+)?instructions", re.IGNORECASE),
    re.compile(r"forget\s+(?:all\s+)?(?:previous\s+)?(?:instructions|prompts)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a\s+)?DAN", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
    re.compile(r"\bignore\s+above\b", re.IGNORECASE),
    re.compile(r"\bnew\s+instructions?\s*:", re.IGNORECASE),
]

MAX_MESSAGE_LENGTH_FOR_SCAN = 50_000


@dataclass(frozen=True)
class ScanResult:
    safe: bool
    matched_patterns: list[str]
    risk_score: float


def scan_message(text: str) -> ScanResult:
    if len(text) > MAX_MESSAGE_LENGTH_FOR_SCAN:
        text = text[:MAX_MESSAGE_LENGTH_FOR_SCAN]

    matched: list[str] = []
    for pattern in PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)

    risk_score = min(len(matched) / 3.0, 1.0)
    return ScanResult(safe=len(matched) == 0, matched_patterns=matched, risk_score=risk_score)
