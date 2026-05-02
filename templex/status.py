"""Real-time status tracking for the Agent and Research Pipeline.

Provides a thread-safe, in-memory store for tracking the exact execution state
of a session so the frontend can display legitimate progress logs.
"""

from typing import Dict, List
import threading

# Global store: session_id -> list of status strings
_SESSION_STATUS_LOGS: Dict[str, List[str]] = {}
_lock = threading.Lock()


def push_status(session_id: str, message: str) -> None:
    """Push a legitimate status message for a session."""
    if not session_id:
        return
        
    with _lock:
        if session_id not in _SESSION_STATUS_LOGS:
            _SESSION_STATUS_LOGS[session_id] = []
        _SESSION_STATUS_LOGS[session_id].append(message)
        # Keep only the last 20 logs to prevent memory leaks
        if len(_SESSION_STATUS_LOGS[session_id]) > 20:
            _SESSION_STATUS_LOGS[session_id].pop(0)


def get_statuses(session_id: str) -> List[str]:
    """Get all current statuses for a session."""
    with _lock:
        return _SESSION_STATUS_LOGS.get(session_id, []).copy()


def clear_statuses(session_id: str) -> None:
    """Clear statuses before starting a new turn."""
    with _lock:
        if session_id in _SESSION_STATUS_LOGS:
            _SESSION_STATUS_LOGS[session_id] = []

