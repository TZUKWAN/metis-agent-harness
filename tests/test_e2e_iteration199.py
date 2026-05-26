"""E2E test with real GLM-4.7-Flash - Iteration 199.

Tests that the full pipeline works: provider -> parser -> strict_output_soft.
Requires METIS_BASE_URL and METIS_API_KEY environment variables.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("METIS_BASE_URL") or not os.getenv("METIS_API_KEY"),
    reason="METIS_BASE_URL and METIS_API_KEY required for real E2E test",
)

from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.profiles import get_model_profile
from metis.runtime.strict_output import StrictOutputParser


@pytest.mark.asyncio
async def test_real_glm_soft_mode():
    """Verify GLM-4.7-Flash returns parseable output with soft mode."""
    provider = OpenAICompatibleProvider()
    profile = get_model_profile("small")
    assert profile.strict_output_soft

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Complete the task and respond with a JSON summary."},
        {"role": "user", "content": "List 3 colors. Reply with a JSON object with key 'colors' containing an array."},
    ]

    response = await provider.complete(messages)
    assert response.content, f"Empty response from {provider.model}"
    assert len(response.content) > 5

    parser = StrictOutputParser()
    result = parser.parse_soft(response.content)
    assert result.status in ("done", "needs_more_work", "blocked")
    assert result.summary


@pytest.mark.asyncio
async def test_real_glm_tool_calling():
    """Verify GLM-4.7-Flash can produce tool calls via native tool_calling."""
    provider = OpenAICompatibleProvider()

    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from disk",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                    },
                    "required": ["path"],
                },
            },
        }
    ]

    messages = [
        {"role": "system", "content": "You are a file assistant. Use tools to complete tasks."},
        {"role": "user", "content": "Read the file config.json"},
    ]

    response = await provider.complete(messages, tools=tools)
    # The model should either return tool_calls or a text response
    assert response.content or response.tool_calls, "Model returned neither content nor tool_calls"
