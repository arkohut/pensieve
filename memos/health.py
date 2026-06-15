"""Capture health: heartbeat tracking and a composite health check.

The record loop touches a heartbeat file every iteration (before the lock check),
so a stale heartbeat unambiguously means the loop stopped ticking — it does NOT go
stale just because the screen is locked. capture_health() composes this with
per-service liveness, a post-wake grace window, and permission/disk probes.
"""
from __future__ import annotations

import platform
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from memos.config import settings
from memos.service_manager import (
    is_service_running,
    is_intentionally_stopped,
    clear_intent_marker,
)

SERVICES = ("record", "serve", "watch")


def heartbeat_path() -> Path:
    return settings.resolved_base_dir / "record.heartbeat"


def touch_heartbeat() -> None:
    """Update the heartbeat file mtime. Called once per record loop iteration."""
    p = heartbeat_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()


def heartbeat_age(now: Optional[float] = None) -> Optional[float]:
    """Seconds since the heartbeat was last touched, or None if it doesn't exist."""
    p = heartbeat_path()
    if not p.exists():
        return None
    now = time.time() if now is None else now
    return now - p.stat().st_mtime


def stale_threshold() -> float:
    """Heartbeat is stale past max(record_interval * factor, floor)."""
    return max(
        settings.record_interval * settings.health.heartbeat_stale_factor,
        settings.health.heartbeat_stale_min_seconds,
    )


def seconds_since_wake(now: Optional[float] = None) -> Optional[float]:
    """Seconds since the machine last woke from sleep (macOS), else None.

    Reads `sysctl -n kern.waketime`, which prints e.g. `{ sec = 1718000000, usec = 0 }`.
    Returns None on non-macOS or any failure, so callers treat it as "no recent wake".
    """
    if platform.system() != "Darwin":
        return None
    try:
        out = subprocess.check_output(["sysctl", "-n", "kern.waketime"], text=True)
    except Exception:
        return None
    m = re.search(r"sec\s*=\s*(\d+)", out)
    if not m:
        return None
    wake = int(m.group(1))
    now = time.time() if now is None else now
    return now - wake


def screen_recording_ok() -> bool:
    """True if macOS screen-recording permission is granted (or N/A off macOS)."""
    if platform.system() != "Darwin":
        return True
    try:
        from Quartz import CGPreflightScreenCaptureAccess
    except ImportError:
        return True
    return bool(CGPreflightScreenCaptureAccess())


def _base_dir() -> Path:
    return settings.resolved_base_dir


def base_dir_writable() -> bool:
    """True if the base directory exists and accepts a probe write."""
    base = _base_dir()
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / ".health_probe"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False
