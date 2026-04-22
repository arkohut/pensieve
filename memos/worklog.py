"""Worklog v2: UTC-timestamped presence log compatible with DB metadata.

v1 (legacy): one line per tick, format `<local_ts> - <screen> - Saved|Skipped (similar to previous)`.
v2 (new):    same line format but timestamp is UTC; first line of file is the marker `# pensieve-worklog v2 utc`.

Reader auto-detects format by presence of header on first non-blank, non-comment line.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .tz_utils import LocalOffset

V2_HEADER = "# pensieve-worklog v2 utc"


@dataclass(frozen=True)
class WorklogEntry:
    ts: str          # raw timestamp string from file
    screen: str
    saved: bool
    is_utc: bool     # True for v2 entries, False for legacy v1


def write_entry(path: Path, utc_ts: str, screen: str, saved: bool, offset: LocalOffset) -> None:
    """Append one entry. Creates file with v2 header if file does not yet exist."""
    path = Path(path)
    file_exists = path.exists() and path.stat().st_size > 0
    status = "Saved" if saved else "Skipped (similar to previous)"
    line = f"{utc_ts} - {screen} - {status}\n"
    with path.open("a") as f:
        if not file_exists:
            f.write(V2_HEADER + "\n")
        f.write(line)


def read_worklog(path: Path) -> Iterator[WorklogEntry]:
    """Yield WorklogEntry objects. Auto-detects v1 vs v2."""
    path = Path(path)
    if not path.exists():
        return
    is_v2 = False
    detected = False
    with path.open() as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            # Detect format on first non-blank line
            if not detected:
                if line.strip() == V2_HEADER:
                    is_v2 = True
                    detected = True
                    continue
                # First line is data -> legacy v1
                detected = True
            # Skip other comments
            if line.startswith("#"):
                continue
            parts = line.split(" - ", 2)
            if len(parts) < 3:
                continue
            ts, screen, status = parts
            yield WorklogEntry(ts=ts, screen=screen, saved=status.startswith("Saved"), is_utc=is_v2)
