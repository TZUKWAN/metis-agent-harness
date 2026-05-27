"""Prompt fragment plugin for Metis."""

from __future__ import annotations

from metis.plugins.api import PluginContext


def register(context: PluginContext) -> None:
    context.register_prompt_fragment(
        "You must always respond in Chinese (中文). "
        "Do not use English unless the user explicitly requests it."
    )
