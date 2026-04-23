"""Deterministic Layer 1 extractor with one narrow job: task identity normalization.

Per spec §5.1: VLM is the primary extractor for all structural fields. Title
regex exists ONLY to produce a stable (tool, title_or_topic) identity for
AI-agent CLI sessions, so the same task does not fragment into multiple
TaskSessions across VLM sampling noise.

Recognized patterns (iTerm2 only):
  `✳ <task>` / `⠐ <task>` / etc.  → tool=Claude Code, title=<task>
  `OC | <topic>`                   → tool=OpenCode,    title=<topic>

Everything else returns `primary.app` only (workspace / contact / url / what
are VLM's job).
"""
from __future__ import annotations
import re
from typing import Optional

from .schema import ExtractedFields, PrimaryRegion

EXTRACTOR_ID = "title_regex_v1"

# Spinner / status characters used by Claude Code (and similar TUIs).
SPINNER_CHARS = r"[✳⠐⠂⠈⠁⠃⠇⠧⠷⠿⣀⣠⣤⣶⣾⣿◇◆▲▼●○✻✽✾✿❈❀↑↓←→⇧⇩⟳⟲◜◝◞◟◠◡⠴⠏⠦⠋⠙⠹]"
SPINNER_RE = re.compile(rf"^\s*(?:{SPINNER_CHARS})+\s*")

OC_TOPIC_RE = re.compile(r"^OC\s*\|\s*(.+)$")

# Bare CLI tool names that indicate idle state (no task identity available).
TUI_IDLE_TITLES = {"Claude Code", "claude", "codex", "OpenCode", "tig", "tmux"}

# A real task title is prose — not an XML-like tag. Reject anything starting
# with `<shorttag>` so CC's internal message envelopes (system-reminder,
# local-command-caveat, user-prompt-submit-hook, plus any future ones) do not
# become canonical task identities. This is intentionally broader than an
# enumerated list so new CC tags don't require memos updates.
NON_TITLE_LEAD_RE = re.compile(r"^\s*<[^>\s]{1,40}>")


def looks_like_non_title(cleaned: str) -> bool:
    """True when `cleaned` starts with an XML-like tag and so is not a real title."""
    return bool(cleaned) and NON_TITLE_LEAD_RE.match(cleaned) is not None


def strip_spinner(s: str) -> str:
    """Remove leading spinner characters + whitespace. Deterministic.

    This is the primitive that gives TaskSession identity stability: two
    screenshots of the same task in different spinner frames canonicalize
    to the same string."""
    return SPINNER_RE.sub("", s or "").strip()


def _minimal(app: Optional[str]) -> ExtractedFields:
    """Return a valid ExtractedFields with only primary.app set."""
    return ExtractedFields(extractor=EXTRACTOR_ID, primary=PrimaryRegion(app=app or ""))


def extract(active_app: Optional[str], active_window: Optional[str]) -> ExtractedFields:
    """Return ExtractedFields. Fills tool + title_or_topic ONLY for recognized
    AI-agent CLI sessions. All other inputs return minimal (app only)."""
    if active_app != "iTerm2":
        return _minimal(active_app)

    win = active_window or ""
    cleaned = strip_spinner(win)

    # Bare tool name (idle) → no identity
    if cleaned in TUI_IDLE_TITLES:
        return _minimal(active_app)

    # Title starts with an XML-like tag → not a real task title (CC's internal
    # message envelopes leak here; see NON_TITLE_LEAD_RE).
    if looks_like_non_title(cleaned):
        return _minimal(active_app)

    # OpenCode: `OC | <topic>`
    m = OC_TOPIC_RE.match(cleaned)
    if m:
        return ExtractedFields(
            extractor=EXTRACTOR_ID,
            primary=PrimaryRegion(
                app=active_app,
                tool="OpenCode",
                title_or_topic=m.group(1).strip(),
            ),
        )

    # Claude Code active task: spinner prefix in original title, cleaned remainder is task
    if SPINNER_RE.match(win) and cleaned:
        return ExtractedFields(
            extractor=EXTRACTOR_ID,
            primary=PrimaryRegion(
                app=active_app,
                tool="Claude Code",
                title_or_topic=cleaned,
            ),
        )

    # Anything else inside iTerm2 → VLM's job
    return _minimal(active_app)
