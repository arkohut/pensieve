"""Runtime predicates about the watch service's processing state.

These are pulled out of memos.cmds.library so that the server route handler
(GET /api/libraries/{id}/processing-status) can ask the same questions
without importing the watch-command module's heavy dependencies.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Tuple

import psutil

from memos.service_manager import get_pid_file


def _pid_file_path() -> Path:
    """Indirection for tests to override."""
    return get_pid_file("watch")


def is_alive() -> bool:
    """Return True if the watch service has a current PID file and that process exists."""
    pid_path = _pid_file_path()
    if not pid_path.exists():
        return False
    try:
        pid_text = pid_path.read_text().strip()
    except OSError:
        return False
    if not pid_text:
        return False
    try:
        pid = int(pid_text)
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def is_on_battery() -> bool:
    """Return True when running on battery power. Defaults to False on systems
    that do not expose a battery sensor (desktops)."""
    battery = psutil.sensors_battery()
    if battery is None:
        return False
    return not battery.power_plugged


def is_within_idle_window(window: Tuple[str, str], now_hhmm: str | None = None) -> bool:
    """Return True when the current wall-clock time falls inside [start, end].

    window is two HH:MM strings. The window may cross midnight (start > end),
    in which case 'inside' means current >= start OR current <= end.

    `now_hhmm` is exposed for tests; production calls pass None to use the
    real clock.
    """
    start = _to_minutes(window[0])
    end = _to_minutes(window[1])
    now = _to_minutes(now_hhmm) if now_hhmm is not None else _to_minutes(datetime.now().strftime("%H:%M"))
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)
