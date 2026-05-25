# Extension Guide

Extensions should use adapters or plugins. They may register `ToolSpec`, prompt fragments, quality gates, role templates, and artifact validators without modifying core runtime modules.

Adapters should expose `health_check()` so the harness can verify path existence and key integration files before exposing adapter tools to an agent.
