"""Credential redaction utility."""

from __future__ import annotations

import re

REDACTION_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}", re.I),
    re.compile(r"(?i)(api[_-]?key|token|password|secret|private[_-]?key)\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"gh[oousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[bpsa]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"https?://[^/\s:]+:[^/\s@]+@"),
    re.compile(r"(mongodb|postgres|mysql|redis)://[^\s]{10,}"),
    re.compile(r"(SECRET|PRIVATE_KEY|PASSWORD|TOKEN)\s*=\s*['\"]?[^'\"\s]{8,}", re.I),
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
