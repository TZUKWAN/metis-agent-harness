"""Graceful shutdown handler for Metis runtime."""

from __future__ import annotations

import signal
import sys
from typing import Any

from metis.logging import get_logger

logger = get_logger("shutdown")

_shutdown_requested = False
_shutdown_reason: str = ""
_pending_state: Any = None
_pending_session_id: str = ""


def is_shutdown_requested() -> bool:
    return _shutdown_requested


def shutdown_reason() -> str:
    return _shutdown_reason


def request_shutdown(reason: str = "manual") -> None:
    global _shutdown_requested, _shutdown_reason
    _shutdown_requested = True
    _shutdown_reason = reason
    logger.info("Shutdown requested: %s", reason)


def register_shutdown_handler(state: Any = None, session_id: str = "") -> None:
    global _pending_state, _pending_session_id
    _pending_state = state
    _pending_session_id = session_id

    def handler(signum: int, frame: Any) -> None:
        global _shutdown_requested, _shutdown_reason
        if _shutdown_requested:
            logger.warning("Second shutdown signal received, forcing exit")
            sys.exit(1)
        _shutdown_requested = True
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        _shutdown_reason = f"signal:{sig_name}"
        logger.info("Shutdown signal received: %s", sig_name)
        if _pending_state is not None and _pending_session_id:
            try:
                _pending_state.record_checkpoint(
                    _pending_session_id,
                    phase="agent.shutdown",
                    status="interrupted",
                    metadata={"signal": signum, "reason": _shutdown_reason},
                )
            except Exception as exc:
                logger.warning("Failed to save shutdown checkpoint: %s", exc)
        sys.exit(130)

    signal.signal(signal.SIGINT, handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handler)
