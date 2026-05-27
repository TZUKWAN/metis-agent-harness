"""Provider factory with pluggable type registry."""

from __future__ import annotations

from typing import Any

from metis.runtime.errors import MetisError

from .base import BaseProvider
from .fake import FakeProvider
from .openai_compat import OpenAICompatibleProvider

_PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {}


def register_provider(provider_type: str, cls: type[BaseProvider]) -> None:
    if not issubclass(cls, BaseProvider):
        raise TypeError(f"{cls} is not a BaseProvider subclass")
    _PROVIDER_REGISTRY[provider_type] = cls


def build_provider(
    *,
    provider_type: str = "openai_compat",
    model: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> BaseProvider:
    cls = _PROVIDER_REGISTRY.get(provider_type)
    if cls is None:
        available = ", ".join(sorted(_PROVIDER_REGISTRY)) or "(none)"
        raise MetisError(f"Unknown provider type '{provider_type}'. Available: {available}")
    if cls is OpenAICompatibleProvider:
        return cls(model=model, base_url=base_url, **kwargs)
    return cls(**kwargs)


register_provider("openai_compat", OpenAICompatibleProvider)
register_provider("fake", FakeProvider)
