"""Credential redaction utility."""

from __future__ import annotations

import re

REDACTION_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}", re.I),
    re.compile(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in REDACTION_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
