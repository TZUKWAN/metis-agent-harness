"""Runtime exception types."""


class MetisError(Exception):
    """Base error for Metis."""


class ProviderError(MetisError):
    """Model provider call failed."""


class ToolDispatchError(MetisError):
    """Tool dispatch failed before returning a structured result."""


class ParserError(MetisError):
    """Tool-call parsing failed."""


class QualityGateError(MetisError):
    """A quality gate failed."""
