import os

import pytest

from metis.providers.openai_compat import OpenAICompatibleProvider
from metis.runtime.errors import ProviderError


@pytest.mark.network
@pytest.mark.asyncio
async def test_bigmodel_openai_compatible_smoke():
    if not os.getenv("METIS_BASE_URL") or not os.getenv("METIS_API_KEY"):
        pytest.skip("METIS_BASE_URL and METIS_API_KEY are not configured")

    provider = OpenAICompatibleProvider()
    try:
        response = await provider.complete(
            [{"role": "user", "content": "Please reply only: Metis API smoke ok"}],
            max_tokens=256,
            temperature=0.1,
        )
    except ProviderError as exc:
        if "429 Too Many Requests" in str(exc):
            pytest.skip(f"External provider is rate limited: {exc}")
        raise

    assert (response.content or response.reasoning or "").strip()
