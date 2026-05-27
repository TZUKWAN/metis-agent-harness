"""Centralized configuration constants for Metis.

All scattered default values should reference this module.
Environment variables take precedence at runtime.
"""

from __future__ import annotations

import os

DEFAULT_MODEL = os.getenv("METIS_MODEL", "glm-4.7-flash")
DEFAULT_MAX_TURNS = 12
DEFAULT_TEMPERATURE = 0.2
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_PROFILE = "small"
DEFAULT_WORKSPACE = "."
DEFAULT_STATE_DB_DIR = ".metis"

MAX_CONTENT_LENGTH = 1_000_000
MAX_TIMEOUT = 600
PER_TURN_TIMEOUT = 120
TOOL_EXECUTION_TIMEOUT = 30
MAX_TOOL_REPAIR_RETRIES = 1
MAX_PARSER_REPAIR_RETRIES = 2
MAX_TOOLS_PER_SESSION = 200

CONTEXT_CHARS_PER_TOKEN = 4
CONTEXT_THRESHOLD = 0.8
COMPRESS_PREVIEW_CHARS = 300

STATE_DB_FILENAME = "state.db"
TOOL_RESULTS_DIR = ".metis/tool-results"
TOOL_DISPATCHER_WORKERS = int(os.getenv("METIS_TOOL_DISPATCHER_WORKERS", "4"))
MAX_SAME_TOOL_PER_SESSION = int(os.getenv("METIS_MAX_SAME_TOOL_PER_SESSION", "20"))

TEMP_BASE = float(os.getenv("METIS_TEMP_BASE", "0.2"))
TEMP_PER_TURN = float(os.getenv("METIS_TEMP_PER_TURN", "0.05"))
TEMP_REPAIR_BOOST = float(os.getenv("METIS_TEMP_REPAIR_BOOST", "0.1"))
TEMP_LOOP_BOOST = float(os.getenv("METIS_TEMP_LOOP_BOOST", "0.15"))
TEMP_MAX = float(os.getenv("METIS_TEMP_MAX", "0.8"))


def validate_config() -> list[str]:
    """Validate all config constants and return a list of warnings."""
    warnings: list[str] = []
    if DEFAULT_MAX_TURNS < 1:
        warnings.append(f"DEFAULT_MAX_TURNS={DEFAULT_MAX_TURNS} must be >= 1")
    if not (0.0 <= DEFAULT_TEMPERATURE <= 2.0):
        warnings.append(f"DEFAULT_TEMPERATURE={DEFAULT_TEMPERATURE} must be in [0, 2]")
    if MAX_CONTENT_LENGTH < 1000:
        warnings.append(f"MAX_CONTENT_LENGTH={MAX_CONTENT_LENGTH} too small (< 1000)")
    if MAX_TIMEOUT < 5:
        warnings.append(f"MAX_TIMEOUT={MAX_TIMEOUT} too small (< 5s)")
    if PER_TURN_TIMEOUT < 5:
        warnings.append(f"PER_TURN_TIMEOUT={PER_TURN_TIMEOUT} too small (< 5s)")
    if TOOL_EXECUTION_TIMEOUT < 1:
        warnings.append(f"TOOL_EXECUTION_TIMEOUT={TOOL_EXECUTION_TIMEOUT} too small (< 1s)")
    if PER_TURN_TIMEOUT > MAX_TIMEOUT:
        warnings.append(f"PER_TURN_TIMEOUT={PER_TURN_TIMEOUT} exceeds MAX_TIMEOUT={MAX_TIMEOUT}")
    if TOOL_EXECUTION_TIMEOUT > MAX_TIMEOUT:
        warnings.append(f"TOOL_EXECUTION_TIMEOUT={TOOL_EXECUTION_TIMEOUT} exceeds MAX_TIMEOUT={MAX_TIMEOUT}")
    if MAX_TOOLS_PER_SESSION < 1:
        warnings.append(f"MAX_TOOLS_PER_SESSION={MAX_TOOLS_PER_SESSION} must be >= 1")
    if CONTEXT_CHARS_PER_TOKEN < 1:
        warnings.append(f"CONTEXT_CHARS_PER_TOKEN={CONTEXT_CHARS_PER_TOKEN} must be >= 1")
    if not (0.1 <= CONTEXT_THRESHOLD <= 1.0):
        warnings.append(f"CONTEXT_THRESHOLD={CONTEXT_THRESHOLD} must be in [0.1, 1.0]")
    if DEFAULT_PORT < 1 or DEFAULT_PORT > 65535:
        warnings.append(f"DEFAULT_PORT={DEFAULT_PORT} must be in [1, 65535]")
    if MAX_TOOL_REPAIR_RETRIES < 0:
        warnings.append(f"MAX_TOOL_REPAIR_RETRIES={MAX_TOOL_REPAIR_RETRIES} must be >= 0")
    if MAX_PARSER_REPAIR_RETRIES < 0:
        warnings.append(f"MAX_PARSER_REPAIR_RETRIES={MAX_PARSER_REPAIR_RETRIES} must be >= 0")
    if not DEFAULT_MODEL:
        warnings.append("DEFAULT_MODEL is empty")
    if DEFAULT_PROFILE not in ("small", "balanced", "deep", "small_strict"):
        warnings.append(f"DEFAULT_PROFILE={DEFAULT_PROFILE} is not a recognized profile")
    return warnings
