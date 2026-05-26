"""Web fetch tool for reading URL content."""

from __future__ import annotations

from typing import Any

import httpx

from metis.config import MAX_CONTENT_LENGTH, MAX_TIMEOUT
from metis.tools.registry import ToolRegistry
from metis.tools.spec import ToolContext, ToolPermissionLevel, ToolSpec


def register_web_tools(registry: ToolRegistry, **kwargs: Any) -> None:
    def web_fetch(args: dict, context: ToolContext) -> dict:
        url = str(args["url"])
        max_length = min(int(args.get("max_length", 10000)), MAX_CONTENT_LENGTH)
        timeout = min(int(args.get("timeout", 15)), MAX_TIMEOUT)

        allowed_schemes = ("http://", "https://")
        if not any(url.startswith(scheme) for scheme in allowed_schemes):
            return {"url": url, "error": "Only HTTP and HTTPS URLs are allowed"}

        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"}
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.hostname in blocked_hosts:
            return {"url": url, "error": "URL points to blocked host"}

        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, max_redirects=5) as client:
                response = client.get(url, headers={"User-Agent": "Metis/1.0"})
                response.raise_for_status()
                content = response.text[:max_length]
                return {
                    "url": url,
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "content": content,
                    "truncated": len(response.text) > max_length,
                }
        except httpx.TimeoutException:
            return {"url": url, "error": f"Request timed out after {timeout}s"}
        except httpx.HTTPStatusError as exc:
            return {"url": url, "error": f"HTTP {exc.response.status_code}", "status_code": exc.response.status_code}
        except httpx.RequestError as exc:
            return {"url": url, "error": f"Request failed: {exc}"}

    registry.register(
        ToolSpec(
            name="web_fetch",
            description="Fetch content from a URL. Returns the text content of the page. Use this to read web pages, API responses, or documentation.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "minLength": 1},
                    "max_length": {"type": "integer", "minimum": 100, "maximum": MAX_CONTENT_LENGTH},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": MAX_TIMEOUT},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            handler=web_fetch,
            category="web",
            side_effect="read",
            permission_level=ToolPermissionLevel.NETWORK.value,
        )
    )
