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
    """Update the heartbeat file mtime. Called once per record loop iteration.

    The base directory is created at import time (config.py), so this stays off
    the hot path (runs every record_interval) and just touches the file.
    """
    heartbeat_path().touch()


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


@dataclass
class CaptureHealth:
    record_up: bool
    serve_up: bool
    watch_up: bool
    heartbeat_age: Optional[float]
    heartbeat_stale: bool
    screen_recording_ok: bool
    base_dir_writable: bool
    problems: List[str]

    @property
    def healthy(self) -> bool:
        return not self.problems


def capture_health(now: Optional[float] = None) -> CaptureHealth:
    """Compute current capture health.

    Side effect: for any service found running that still carries a `pen stop`
    intent marker, the marker is cleared here. This is intentional — it lets a
    service that came back on its own (e.g. relaunched at login by launchd
    RunAtLoad after a `pen stop` followed by reboot) resume being monitored.
    Callers using this only to display status should know it may clear stale markers.

    A running `record` with no heartbeat file yet (heartbeat_age is None) is treated
    as stale and flagged, since the loop has not yet proven it is ticking.
    """
    now = time.time() if now is None else now
    ups = {svc: is_service_running(svc)[0] for svc in SERVICES}

    age = heartbeat_age(now)
    threshold = stale_threshold()
    stale = age is None or age > threshold

    since_wake = seconds_since_wake(now)
    in_wake_grace = since_wake is not None and since_wake < settings.health.wake_grace_seconds

    problems: List[str] = []

    # record: liveness is critical; only flag heartbeat staleness when it's up.
    if not ups["record"]:
        if not is_intentionally_stopped("record"):
            problems.append("record process is not running")
    else:
        clear_intent_marker("record")  # it's up; forget any stale stop marker
        if stale and not in_wake_grace:
            problems.append("record heartbeat is stale (capture loop not ticking)")

    # serve/watch: report when down unless intentionally stopped.
    for svc in ("serve", "watch"):
        if not ups[svc]:
            if not is_intentionally_stopped(svc):
                problems.append(f"{svc} process is not running")
        else:
            clear_intent_marker(svc)

    sr_ok = screen_recording_ok()
    if not sr_ok:
        problems.append("screen recording permission not granted")

    writable = base_dir_writable()
    if not writable:
        problems.append("base directory is not writable (disk full?)")

    return CaptureHealth(
        record_up=ups["record"],
        serve_up=ups["serve"],
        watch_up=ups["watch"],
        heartbeat_age=age,
        heartbeat_stale=stale,
        screen_recording_ok=sr_ok,
        base_dir_writable=writable,
        problems=problems,
    )
