"""Error classification for recovery decisions."""

from __future__ import annotations


class ErrorCategory:
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    PROVIDER = "provider"
    CONTEXT = "context"
    PARSER = "parser"
    TOOL = "tool"
    VALIDATION = "validation"
    SECURITY = "security"
    UNKNOWN = "unknown"


class ErrorClassifier:
    RULES = [
        (ErrorCategory.RATE_LIMIT, ("rate limit", "429", "too many requests", "quota", "rate_limit", "rate-limit", "slow down")),
        (ErrorCategory.AUTH, ("401", "403", "unauthorized", "forbidden", "invalid api key", "authentication", "api_key", "access token")),
        (ErrorCategory.NETWORK, ("timeout", "connection", "dns", "network", "temporarily unavailable", "connectionrefused", "connection refused", "eof occurred", "connection reset", "broken pipe", "ssl error", "certifi")),
        (ErrorCategory.CONTEXT, ("context length", "maximum context", "token limit", "too many tokens", "context window", "max_tokens")),
        (ErrorCategory.PARSER, ("parsererror", "parse", "invalid json", "tool call", "jsondecodeerror", "unexpected token", "unterminated string")),
        (ErrorCategory.SECURITY, ("permission denied", "path escapes", "blocked by security", "prompt injection", "is_read_denied", "is_write_denied", "path security", "ssrf", "workspace boundary")),
        (ErrorCategory.VALIDATION, ("validation", "schema", "required field", "invalid input", "argument schema", "not in enum", "additional property")),
        (ErrorCategory.TOOL, ("tool", "subprocess", "filenotfounderror", "runtimeerror", "command not found", "exit_code", "timed out", "no such file")),
        (ErrorCategory.PROVIDER, ("provider", "model", "upstream", "server error", "500", "502", "503", "overloaded", "capacity", "service unavailable")),
    ]

    def classify(self, error: BaseException | str) -> str:
        text = str(error).lower()
        for category, needles in self.RULES:
            if any(needle in text for needle in needles):
                return category
        return ErrorCategory.UNKNOWN
