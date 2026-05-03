"""Thread-safe session status log store.

Used by the pipeline to push real-time progress updates that the
frontend can poll via GET /api/chat/status/{session_id}.
"""

import threading
from typing import Dict, List

_lock = threading.Lock()
_session_logs: Dict[str, List[str]] = {}


def push_status(session_id: str, message: str) -> None:
    """Append a status message for the given session."""
    with _lock:
        if session_id not in _session_logs:
            _session_logs[session_id] = []
        _session_logs[session_id].append(message)


def get_status_logs(session_id: str) -> List[str]:
    """Return a copy of all status logs for the given session."""
    with _lock:
        return list(_session_logs.get(session_id, []))


def clear_status_logs(session_id: str) -> None:
    """Clear status logs for the given session (call before each new turn)."""
    with _lock:
        _session_logs[session_id] = []
