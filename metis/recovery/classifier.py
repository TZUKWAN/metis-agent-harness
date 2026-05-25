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
        (ErrorCategory.RATE_LIMIT, ("rate limit", "429", "too many requests", "quota")),
        (ErrorCategory.AUTH, ("401", "403", "unauthorized", "forbidden", "invalid api key", "authentication")),
        (ErrorCategory.NETWORK, ("timeout", "connection", "dns", "network", "temporarily unavailable")),
        (ErrorCategory.CONTEXT, ("context length", "maximum context", "token limit", "too many tokens")),
        (ErrorCategory.PARSER, ("parsererror", "parse", "invalid json", "tool call")),
        (ErrorCategory.SECURITY, ("permission denied", "path escapes", "blocked by security", "prompt injection")),
        (ErrorCategory.VALIDATION, ("validation", "schema", "required field", "invalid input")),
        (ErrorCategory.TOOL, ("tool", "subprocess", "filenotfounderror", "runtimeerror")),
        (ErrorCategory.PROVIDER, ("provider", "model", "upstream", "server error", "500", "502", "503")),
    ]

    def classify(self, error: BaseException | str) -> str:
        text = str(error).lower()
        for category, needles in self.RULES:
            if any(needle in text for needle in needles):
                return category
        return ErrorCategory.UNKNOWN
