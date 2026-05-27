"""Token estimation for context budget calculations.

Metis needs an approximate token count without dragging in heavy tokenizers
(tiktoken, transformers) as hard dependencies.  The estimator below uses
language-aware heuristics that are good enough for budget decisions.

Accuracy targets:
- English-dominant text: ±15% of tiktoken cl100k_base
- Chinese-dominant text: ±20% of model-specific CJK tokenizers
- Mixed text: ±25%

For production-grade accuracy, swap in a real tokenizer via the
``TokenEstimator`` protocol.
"""

from __future__ import annotations

from typing import Protocol


class TokenEstimator(Protocol):
    """Protocol for token-count implementations."""

    def estimate(self, text: str) -> int:
        ...


class CharTokenEstimator:
    """Naive fallback: 1 token ≈ N characters (configurable)."""

    def __init__(self, chars_per_token: float = 4.0) -> None:
        self.chars_per_token = chars_per_token

    def estimate(self, text: str) -> int:
        return int(len(text) / max(0.1, self.chars_per_token))


class LanguageAwareTokenEstimator:
    """Estimate tokens with language-aware character density.

    CJK text is much denser (fewer chars per token) than Latin text.
    This estimator detects the script mix and picks a density factor.
    """

    # Empirical density factors (chars per token)
    DENSITY_CJK = 1.3
    DENSITY_MIXED = 2.0
    DENSITY_LATIN = 3.8
    DENSITY_CODE = 3.5  # code / JSON has lots of punctuation

    def __init__(self, default_density: float | None = None) -> None:
        self.default_density = default_density

    def estimate(self, text: str) -> int:
        if not text:
            return 0
        density = self._detect_density(text)
        return int(len(text) / density)

    def _detect_density(self, text: str) -> float:
        if self.default_density is not None:
            return self.default_density

        total = len(text)
        if total == 0:
            return self.DENSITY_LATIN

        cjk = self._count_cjk(text)
        latin = self._count_latin(text)
        code_markers = text.count("{") + text.count("}") + text.count("[") + text.count("]")
        code_ratio = code_markers / max(1, total)

        cjk_ratio = cjk / total
        latin_ratio = latin / total

        # Heuristic blend
        if cjk_ratio > 0.6:
            base = self.DENSITY_CJK
        elif cjk_ratio > 0.25:
            base = self.DENSITY_MIXED
        elif code_ratio > 0.05:
            base = self.DENSITY_CODE
        else:
            base = self.DENSITY_LATIN

        # Fine-tune: lots of punctuation pushes density down
        punct = sum(1 for c in text if c in "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
        punct_ratio = punct / total
        if punct_ratio > 0.15:
            base *= 0.85

        return max(1.0, base)

    @staticmethod
    def _count_cjk(text: str) -> int:
        """Count CJK unified ideographs and extensions."""
        count = 0
        for ch in text:
            cp = ord(ch)
            # CJK Unified Ideographs + Extensions A-D
            if (
                (0x4E00 <= cp <= 0x9FFF)
                or (0x3400 <= cp <= 0x4DBF)
                or (0x20000 <= cp <= 0x2A6DF)
                or (0x2A700 <= cp <= 0x2B73F)
                or (0x2B740 <= cp <= 0x2B81F)
                or (0xF900 <= cp <= 0xFAFF)
            ):
                count += 1
        return count

    @staticmethod
    def _count_latin(text: str) -> int:
        """Count basic Latin / ASCII characters."""
        return sum(1 for ch in text if ch.isascii() and ch.isalpha())


class CompositeTokenEstimator:
    """Estimate tokens for a list of messages + optional tool schemas.

    Uses LanguageAwareTokenEstimator for natural-language content and
    CharTokenEstimator for structured content (JSON schemas).
    """

    def __init__(self) -> None:
        self.text_estimator = LanguageAwareTokenEstimator()
        self.json_estimator = CharTokenEstimator(chars_per_token=3.5)

    def estimate_messages(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            content = str(msg.get("content", ""))
            reasoning = str(msg.get("reasoning_content", ""))
            total += self.text_estimator.estimate(content)
            total += self.text_estimator.estimate(reasoning)
            # tool_calls JSON also costs tokens
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                import json
                total += self.json_estimator.estimate(json.dumps(tool_calls, ensure_ascii=False))
        return total

    def estimate_tool_schemas(self, tool_schemas: list[dict]) -> int:
        import json
        text = json.dumps(tool_schemas, ensure_ascii=False)
        return self.json_estimator.estimate(text)

    def estimate_total(self, messages: list[dict], tool_schemas: list[dict] | None = None) -> int:
        total = self.estimate_messages(messages)
        if tool_schemas:
            total += self.estimate_tool_schemas(tool_schemas)
        return total


def get_default_estimator() -> TokenEstimator:
    return CompositeTokenEstimator()
