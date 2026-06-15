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
