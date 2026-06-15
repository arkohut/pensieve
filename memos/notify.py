"""Desktop notifications + alert throttling for capture-health problems."""
from __future__ import annotations

import json
import logging
import platform
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from memos.config import settings


def _escape(text: str) -> str:
    """Make text safe inside an AppleScript double-quoted string."""
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def notify(title: str, message: str) -> None:
    """Show a desktop notification. macOS only for now; never raises."""
    try:
        if platform.system() == "Darwin":
            script = f'display notification "{_escape(message)}" with title "{_escape(title)}"'
            subprocess.run(["osascript", "-e", script], check=False)
        else:
            logging.info("notify (no desktop channel on this OS): %s — %s", title, message)
    except Exception as e:  # notifications must never break the health check
        logging.warning("notify failed: %s", e)


def _state_path() -> Path:
    return settings.resolved_base_dir / "health.state"


def _read_state(state_path: Path) -> dict:
    try:
        return json.loads(state_path.read_text())
    except (OSError, ValueError):
        return {}


def _write_state(state_path: Path, problems: List[str], alerted_at: float) -> None:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"problems": sorted(problems), "alerted_at": alerted_at}))
    except OSError as e:
        logging.warning("could not write health state: %s", e)


def alert_if_changed(
    problems: List[str],
    now: Optional[float] = None,
    state_path: Optional[Path] = None,
    cooldown: Optional[int] = None,
) -> Optional[str]:
    """Notify only when the problem set changes or the cooldown elapses.

    Returns 'problem' when a problem alert was sent, 'recovered' when a recovery
    alert was sent, or None when nothing was sent.
    """
    now = time.time() if now is None else now
    state_path = _state_path() if state_path is None else state_path
    cooldown = settings.health.alert_cooldown_seconds if cooldown is None else cooldown

    prev = _read_state(state_path)
    prev_problems = set(prev.get("problems", []))
    prev_alerted_at = prev.get("alerted_at", 0)

    if problems:
        changed = set(problems) != prev_problems
        cooled = (now - prev_alerted_at) >= cooldown
        if changed or cooled:
            notify("Pensieve", "Screen capture issue:\n" + "\n".join(problems))
            _write_state(state_path, problems, now)
            return "problem"
        # Same problems within cooldown: the persisted state is already current.
        return None

    # No problems now.
    if prev_problems:
        notify("Pensieve", "Screen capture recovered.")
        _write_state(state_path, [], now)
        return "recovered"
    # Already healthy: nothing changed, nothing to persist.
    return None
