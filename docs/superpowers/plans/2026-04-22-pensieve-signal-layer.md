# Pensieve Signal Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-screenshot structured metadata is reliably populated for new captures and backfilled for the last 30 days, so downstream layers can build on a clean signal.

**Architecture:** Two extractors write into versioned metadata fields per entity. `title_regex_v1` runs at the recorder's plugin pipeline (cheap, deterministic). `structured_vlm_v1_qwen36_35b` runs as a FastAPI plugin similar to existing `vlm/`, with a versioned prompt and JSON output. A backfill CLI command processes existing screenshots in batches. Worklog format migrates to UTC to match DB.

**Tech Stack:** Python 3.10+, FastAPI plugin pattern (existing), pytest (new), httpx, Pydantic v2, psycopg2 (existing).

**Spec reference:** `docs/superpowers/specs/2026-04-22-pensieve-activity-model-design.md` §4 (TZ), §5 (Layer 1), §10 (backfill).

**POC reference:** `docs/superpowers/experiments/vlm_bench/` (12 sample entities + qwen baseline + kimi comparison).

---

## File structure

New files:

- `tests/conftest.py` — pytest fixtures (sample entities, worklog samples, mock VLM responses)
- `tests/test_tz.py` — TZ helper unit tests
- `tests/test_extractors_title_regex.py` — title regex unit tests (12 cases)
- `tests/test_extractors_schema.py` — Pydantic schema tests
- `tests/test_plugin_structured_vlm.py` — plugin unit + mocked-endpoint tests
- `tests/test_cmd_backfill.py` — backfill CLI tests
- `tests/test_worklog.py` — v2 format reader + writer tests
- `tests/fixtures/screenshots/` — 5 representative `.webp` files copied from real entities (small subset of POC samples)
- `tests/fixtures/vlm_responses/` — JSON responses for each test scenario

- `memos/tz_utils.py` — UTC↔local conversion helpers
- `memos/extractors/__init__.py`
- `memos/extractors/schema.py` — `ExtractedFields` Pydantic model (shared by both extractors)
- `memos/extractors/title_regex.py` — `extract(active_app, active_window) → ExtractedFields`
- `memos/plugins/structured_vlm/__init__.py`
- `memos/plugins/structured_vlm/main.py` — FastAPI plugin (forks from `vlm/main.py` shape)
- `memos/plugins/structured_vlm/prompt_v1.py` — wraps the asset
- `memos/plugins/structured_vlm/prompt_v1.txt` — the structured-JSON prompt asset (copied from vlm_bench)
- `memos/plugins/structured_vlm/requirements.txt` — `httpx`, `fastapi`, `pydantic`
- `memos/cmds/backfill.py` — typer command group with `structured-vlm` subcommand
- `memos/worklog.py` — v2 worklog reader/writer (extracted from `record.py`)

Modified files:

- `pyproject.toml` — add `[tool.pytest.ini_options]`, add `pytest`, `pytest-asyncio`, `respx` to optional `[project.optional-dependencies] test`
- `memos/config.py` — add `StructuredVLMSettings` class; add `structured_vlm` field to top-level `Settings`
- `memos/server.py` — wire `structured_vlm` plugin router after VLM init (~ line 1148)
- `memos/record.py` — replace `worklog.write(...)` with `memos.worklog.write_entry(...)`; switch to UTC timestamps; add v2 header on file create
- `memos/cmds/__init__.py` (or wherever `app = typer.Typer()` is composed) — register the new `backfill_app`

Removed: nothing.

---

## Task 1: Test infrastructure + TZ helpers

Pytest doesn't exist in this project today. We add minimal config and a single
working test (TZ helpers) so all later tasks have a place to write tests.

**Files:**
- Create: `pyproject.toml` (modify) — add pytest config + test deps
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_tz.py`
- Create: `memos/tz_utils.py`

- [ ] **Step 1.1: Add pytest to optional dependencies**

Edit `pyproject.toml`. Add a `test` group under `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
postgresql = [ "psycopg2-binary",]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.20",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 1.2: Install test deps**

Run: `uv pip install -e '.[test]'`
Expected: pytest, pytest-asyncio, respx installed.

- [ ] **Step 1.3: Create empty test infrastructure**

```bash
mkdir -p tests/fixtures/screenshots tests/fixtures/vlm_responses
touch tests/__init__.py tests/conftest.py
```

- [ ] **Step 1.4: Write failing TZ test**

Create `tests/test_tz.py`:

```python
from datetime import datetime, timedelta
import pytest

from memos.tz_utils import (
    local_date_to_utc_range,
    utc_ts_to_local_dt,
    local_ts_to_utc,
    LocalOffset,
)

UTC8 = LocalOffset.from_string("+08:00")


def test_local_date_to_utc_range_china():
    """Local 2026-04-17 (UTC+8) maps to UTC [2026-04-16 16:00, 2026-04-17 16:00)."""
    start, end = local_date_to_utc_range("20260417", UTC8)
    assert start == "20260416-160000"
    assert end == "20260417-160000"


def test_utc_to_local_china():
    """UTC 20260417-064639 = Local 20260417-144639 in UTC+8."""
    local_dt = utc_ts_to_local_dt("20260417-064639", UTC8)
    assert local_dt.strftime("%Y%m%d-%H%M%S") == "20260417-144639"


def test_local_to_utc_round_trip():
    """Local→UTC→local should be identity."""
    local_str = "20260417-144639"
    utc_str = local_ts_to_utc(local_str, UTC8)
    back_local = utc_ts_to_local_dt(utc_str, UTC8)
    assert back_local.strftime("%Y%m%d-%H%M%S") == local_str


def test_offset_parse_and_format():
    """Offset accepts +HH:MM and -HH:MM strings."""
    assert LocalOffset.from_string("+08:00").seconds == 8 * 3600
    assert LocalOffset.from_string("-05:30").seconds == -(5 * 3600 + 30 * 60)
    assert LocalOffset.from_string("+08:00").to_string() == "+08:00"


def test_offset_from_system():
    """LocalOffset.from_system() returns the running machine's offset, not a hardcoded value."""
    offset = LocalOffset.from_system()
    # We don't assert a specific value (depends on test machine), but it must be a valid offset
    assert -14 * 3600 <= offset.seconds <= 14 * 3600
```

- [ ] **Step 1.5: Run test, expect import failure**

Run: `pytest tests/test_tz.py -v`
Expected: `ImportError: No module named 'memos.tz_utils'`

- [ ] **Step 1.6: Implement `memos/tz_utils.py`**

Create `memos/tz_utils.py`:

```python
"""Timezone helpers for converting between UTC (DB storage) and local time (UI/worklog)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class LocalOffset:
    """Local TZ offset in seconds from UTC. Positive for east of UTC."""
    seconds: int

    @classmethod
    def from_string(cls, s: str) -> "LocalOffset":
        """Parse '+HH:MM' or '-HH:MM' into LocalOffset."""
        sign = 1 if s[0] == "+" else -1
        hours, minutes = s[1:].split(":")
        return cls(sign * (int(hours) * 3600 + int(minutes) * 60))

    @classmethod
    def from_system(cls) -> "LocalOffset":
        """Read the local TZ offset from the OS at call time.

        Uses the current offset (including DST if active), not the standard-time
        offset. This matters for users in DST regions — Task 6's backfill CLI
        converts 'last N days local' to a UTC range and must use the offset that
        was in effect at that moment.
        """
        return cls(int(datetime.now().astimezone().utcoffset().total_seconds()))

    def to_string(self) -> str:
        sign = "+" if self.seconds >= 0 else "-"
        total = abs(self.seconds)
        return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def local_date_to_utc_range(local_date_str: str, offset: LocalOffset) -> tuple[str, str]:
    """Given a local date YYYYMMDD, return the UTC [start, end) range as YYYYMMDD-HHMMSS strings."""
    local_start = datetime.strptime(local_date_str, "%Y%m%d")
    utc_start = local_start - timedelta(seconds=offset.seconds)
    utc_end = utc_start + timedelta(days=1)
    return utc_start.strftime("%Y%m%d-%H%M%S"), utc_end.strftime("%Y%m%d-%H%M%S")


def utc_ts_to_local_dt(ts_str: str, offset: LocalOffset) -> datetime:
    """Parse a UTC timestamp and return local datetime."""
    utc = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
    return utc + timedelta(seconds=offset.seconds)


def local_ts_to_utc(ts_str: str, offset: LocalOffset) -> str:
    """Parse a local timestamp and return UTC string."""
    local = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
    utc = local - timedelta(seconds=offset.seconds)
    return utc.strftime("%Y%m%d-%H%M%S")
```

- [ ] **Step 1.7: Run tests, expect pass**

Run: `pytest tests/test_tz.py -v`
Expected: 5 passed.

- [ ] **Step 1.8: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/conftest.py tests/test_tz.py memos/tz_utils.py
git commit -m "test: add pytest infra and TZ utilities"
```

---

## Task 2: Layer 1 extraction schema

A Pydantic model shared by both extractors. Single source of truth for the
output shape; both `title_regex_v1` and `structured_vlm_v1_*` produce
instances of this model.

**Files:**
- Create: `memos/extractors/__init__.py`
- Create: `memos/extractors/schema.py`
- Create: `tests/test_extractors_schema.py`

- [ ] **Step 2.1: Write failing schema test**

Create `tests/test_extractors_schema.py`:

```python
import json
import pytest
from pydantic import ValidationError

from memos.extractors.schema import (
    ExtractedFields, PrimaryRegion, SecondaryRegion, Confidence
)


def test_minimal_valid_extraction():
    """The minimum required: extractor id + a primary.app."""
    e = ExtractedFields(
        extractor="title_regex_v1",
        primary=PrimaryRegion(app="iTerm2"),
    )
    assert e.extractor == "title_regex_v1"
    assert e.primary.app == "iTerm2"
    assert e.primary.tool is None
    assert e.primary.workspace is None
    assert e.secondary == []
    assert e.contact is None
    assert e.url is None
    assert e.notes is None


def test_full_extraction_round_trip():
    """A fully populated extraction serializes to JSON and back unchanged."""
    e = ExtractedFields(
        extractor="structured_vlm_v1_qwen36_35b",
        primary=PrimaryRegion(
            app="iTerm2",
            tool="Claude Code",
            what="Debug gear controller blocking issue with bayesjob",
            title_or_topic="Debug gear controller blocking issue with bayesjob",
            workspace="openbayes-gear-controller",
        ),
        secondary=[SecondaryRegion(app="iTerm2", what="git diff in adjacent pane")],
        contact=None,
        url="http://localhost:5174/",
        confidence=Confidence(primary="high", contact=None, url="high"),
        notes="iTerm2 split-pane: top pane Claude Code, bottom pane shell",
    )
    j = e.model_dump_json()
    e2 = ExtractedFields.model_validate_json(j)
    assert e2 == e


def test_tool_field_is_optional():
    """primary.tool is optional; VLM typically leaves it null, title regex fills it."""
    e = ExtractedFields(
        extractor="structured_vlm_v1_qwen36_35b",
        primary=PrimaryRegion(app="Google Chrome"),
    )
    assert e.primary.tool is None


def test_parse_from_vlm_json_response():
    """Parsing a real VLM JSON response (matching the prompt v1 contract) succeeds
    even though the VLM does not emit primary.tool."""
    raw = json.dumps({
        "primary": {
            "app": "iTerm2",
            "what": "在终端中执行 git pull",
            "title_or_topic": "hyperai-next git:(master)",
            "workspace": "hyperai-next",
        },
        "secondary": [],
        "contact": None,
        "url": None,
        "confidence": {"primary": "high", "contact": None, "url": None},
        "notes": "macOS, iTerm2 single window",
    })
    parsed = json.loads(raw)
    e = ExtractedFields(extractor="structured_vlm_v1_qwen36_35b", **parsed)
    assert e.primary.workspace == "hyperai-next"
    assert e.primary.tool is None  # VLM didn't specify; leave null


def test_confidence_value_constraints():
    """Confidence values must be in {high, medium, low, null}."""
    Confidence(primary="high")  # ok
    Confidence(primary="medium")  # ok
    Confidence(primary="low")  # ok
    Confidence(primary=None)  # ok
    with pytest.raises(ValidationError):
        Confidence(primary="extreme")  # not in enum
```

- [ ] **Step 2.2: Run tests, expect import failure**

Run: `pytest tests/test_extractors_schema.py -v`
Expected: ImportError on `memos.extractors.schema`.

- [ ] **Step 2.3: Implement schema**

Create `memos/extractors/__init__.py` (empty):

```python
```

Create `memos/extractors/schema.py`:

```python
"""Layer 1 extraction output schema. Shared by all extractors (title_regex, structured_vlm)."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field

ConfidenceLevel = Literal["high", "medium", "low"]


class PrimaryRegion(BaseModel):
    app: str
    # Tool is the AI CLI running inside iTerm, when identifiable: "Claude Code" or "OpenCode".
    # VLM leaves this null; title_regex_v1 fills it when spinner/prefix is recognized.
    # Used by Layer 2 to form TaskSession identity key (tool, title_or_topic).
    tool: Optional[str] = None
    what: Optional[str] = None
    title_or_topic: Optional[str] = None
    workspace: Optional[str] = None


class SecondaryRegion(BaseModel):
    app: str
    what: Optional[str] = None


class Confidence(BaseModel):
    primary: Optional[ConfidenceLevel] = None
    contact: Optional[ConfidenceLevel] = None
    url: Optional[ConfidenceLevel] = None


class ExtractedFields(BaseModel):
    """The unified Layer 1 output. Both title_regex_v1 and structured_vlm_v1_* produce this."""
    extractor: str = Field(..., description="Identifier of the extractor and version, e.g., 'title_regex_v1' or 'structured_vlm_v1_qwen36_35b'")
    primary: PrimaryRegion
    secondary: list[SecondaryRegion] = Field(default_factory=list)
    contact: Optional[str] = None
    url: Optional[str] = None
    confidence: Confidence = Field(default_factory=Confidence)
    notes: Optional[str] = None
```

- [ ] **Step 2.4: Run tests, expect pass**

Run: `pytest tests/test_extractors_schema.py -v`
Expected: 5 passed.

- [ ] **Step 2.5: Commit**

```bash
git add memos/extractors/__init__.py memos/extractors/schema.py tests/test_extractors_schema.py
git commit -m "feat(extractors): add Layer 1 extraction schema"
```

---

## Task 3: Title regex extractor (scope: task identity normalization only)

Per spec §5.1, title regex has **one narrow job**: produce a deterministic
`primary.tool` + canonical `primary.title_or_topic` for AI-agent CLI
sessions (Claude Code `✳ <task>`, OpenCode `OC | <topic>`). This is used by
Layer 2 as the stable TaskSession identity key so the same task does not
fragment into multiple sessions across VLM sampling noise.

Everything else (workspace, contact, url, secondary, what) is VLM's job.
Title regex leaves those fields null by design.

**Files:**
- Create: `memos/extractors/title_regex.py`
- Create: `tests/test_extractors_title_regex.py`

- [ ] **Step 3.1: Write failing tests for the narrow scope**

Create `tests/test_extractors_title_regex.py`:

```python
import pytest
from memos.extractors.title_regex import extract, strip_spinner
from memos.extractors.schema import ExtractedFields


# strip_spinner unit tests: the core normalization primitive.

@pytest.mark.parametrize("raw,expected", [
    ("✳ Debug gear controller", "Debug gear controller"),
    ("⠐ Debug gear controller", "Debug gear controller"),
    ("⠂ Debug gear controller", "Debug gear controller"),
    ("◇ Debug gear controller", "Debug gear controller"),
    ("✳  Debug gear controller", "Debug gear controller"),       # double space
    ("Debug gear controller", "Debug gear controller"),           # no spinner
    ("", ""),
])
def test_strip_spinner(raw, expected):
    assert strip_spinner(raw) == expected


# The only cases extract() produces non-null fields: CC spinner + OpenCode OC|.

def test_cc_spinner_produces_tool_and_canonical_title():
    """Spinner prefix → primary.tool='Claude Code' + canonical title (stripped)."""
    result = extract("iTerm2", "✳ Debug gear controller blocking issue with bayesjob")
    assert result.extractor == "title_regex_v1"
    assert result.primary.app == "iTerm2"
    assert result.primary.tool == "Claude Code"
    assert result.primary.title_or_topic == "Debug gear controller blocking issue with bayesjob"
    # All other fields stay null (VLM's job)
    assert result.primary.workspace is None
    assert result.primary.what is None
    assert result.contact is None
    assert result.url is None


def test_cc_spinner_variants_produce_same_canonical_title():
    """Different spinner frames of the same task → identical (tool, title) identity.
    This is the whole point of title regex: TaskSession stability."""
    titles = [
        "✳ Migrate Svelte frontend to React",
        "⠐ Migrate Svelte frontend to React",
        "⠂ Migrate Svelte frontend to React",
        "◇ Migrate Svelte frontend to React",
    ]
    results = [extract("iTerm2", t) for t in titles]
    task_identities = {(r.primary.tool, r.primary.title_or_topic) for r in results}
    assert len(task_identities) == 1
    assert task_identities == {("Claude Code", "Migrate Svelte frontend to React")}


def test_opencode_oc_prefix_produces_tool_and_canonical_topic():
    """`OC | <topic>` → primary.tool='OpenCode' + canonical topic."""
    result = extract("iTerm2", "OC | Cloudflare edge auth 获取 IP 失败")
    assert result.primary.tool == "OpenCode"
    assert result.primary.title_or_topic == "Cloudflare edge auth 获取 IP 失败"
    assert result.primary.workspace is None


def test_bare_tool_name_produces_no_identity():
    """Bare 'claude' / 'codex' / 'OpenCode' (no task): app only, tool/title null."""
    for title in ["claude", "codex", "OpenCode", "tig"]:
        result = extract("iTerm2", title)
        assert result.primary.app == "iTerm2"
        assert result.primary.tool is None
        assert result.primary.title_or_topic is None


def test_non_agent_iterm_title_produces_app_only():
    """fish prompts / bash prompts / other iTerm windows: VLM's job, not title regex.
    Title regex leaves tool and title_or_topic null for these."""
    cases = [
        "fish /Users/shanchuanxu/projects/memos",
        "shanchuanxu@host:~/projects/memos",
        "[hyperai] m11",
        "kubectl get pods -w",
    ]
    for title in cases:
        result = extract("iTerm2", title)
        assert result.primary.app == "iTerm2"
        assert result.primary.tool is None
        assert result.primary.title_or_topic is None
        assert result.primary.workspace is None  # VLM's job


def test_non_iterm_app_produces_app_only():
    """Non-iTerm apps (browsers, chat, IDE, anything) → app only, all else null."""
    cases = [
        ("Google Chrome", "Some page title"),
        ("微信", "张玲"),
        ("Cursor", "library.py — memos"),
        ("Antigravity", "hyperai-next"),
    ]
    for app, title in cases:
        result = extract(app, title)
        assert result.primary.app == app
        assert result.primary.tool is None
        assert result.primary.title_or_topic is None


def test_extract_handles_none_inputs():
    """None or empty inputs do not crash."""
    result = extract(None, None)
    assert result.primary.app == ""
    assert result.primary.tool is None

    result = extract("iTerm2", None)
    assert result.primary.app == "iTerm2"
    assert result.primary.tool is None
```

- [ ] **Step 3.2: Run tests, expect import failure**

Run: `pytest tests/test_extractors_title_regex.py -v`
Expected: ImportError on `memos.extractors.title_regex`.

- [ ] **Step 3.3: Implement the narrowly-scoped extractor**

Create `memos/extractors/title_regex.py`:

```python
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
```

- [ ] **Step 3.4: Run tests, expect pass**

Run: `pytest tests/test_extractors_title_regex.py -v`
Expected: ~18 passed (7 parametrized `strip_spinner` + 7 test functions, some with multiple asserts).

- [ ] **Step 3.5: Commit**

```bash
git add memos/extractors/title_regex.py tests/test_extractors_title_regex.py
git commit -m "feat(extractors): add task identity normalizer (title regex v1)"
```

---

## Task 4: Worklog v2 (UTC) format

The recorder currently writes worklog entries in local time, which mismatches
the DB's UTC `timestamp` metadata. Migrate to v2 format with UTC timestamps
and a header marker. Reader supports both v1 (legacy) and v2.

**Files:**
- Create: `memos/worklog.py`
- Create: `tests/test_worklog.py`
- Modify: `memos/record.py:313` (write call site)

- [ ] **Step 4.1: Write failing worklog tests**

Create `tests/test_worklog.py`:

```python
from pathlib import Path
import pytest

from memos.worklog import (
    WorklogEntry, write_entry, read_worklog, V2_HEADER,
)
from memos.tz_utils import LocalOffset

UTC8 = LocalOffset.from_string("+08:00")


def test_v2_writer_creates_header_on_new_file(tmp_path):
    """Writing to a new file auto-creates the v2 header line."""
    p = tmp_path / "worklog"
    write_entry(p, "20260417-064639", "color_lcd", saved=True, offset=UTC8)
    content = p.read_text().splitlines()
    assert content[0] == V2_HEADER
    # Entry timestamp must be UTC (input was already UTC string)
    assert content[1] == "20260417-064639 - color_lcd - Saved"


def test_v2_writer_does_not_duplicate_header(tmp_path):
    p = tmp_path / "worklog"
    write_entry(p, "20260417-064639", "color_lcd", saved=True, offset=UTC8)
    write_entry(p, "20260417-064643", "color_lcd", saved=False, offset=UTC8)
    lines = p.read_text().splitlines()
    assert lines.count(V2_HEADER) == 1
    assert lines[2] == "20260417-064643 - color_lcd - Skipped (similar to previous)"


def test_v2_reader_parses_utc_timestamps(tmp_path):
    p = tmp_path / "worklog"
    p.write_text(V2_HEADER + "\n"
                 "20260417-064639 - color_lcd - Saved\n"
                 "20260417-064643 - color_lcd - Skipped (similar to previous)\n")
    entries = list(read_worklog(p))
    assert len(entries) == 2
    assert entries[0] == WorklogEntry(ts="20260417-064639", screen="color_lcd", saved=True, is_utc=True)
    assert entries[1] == WorklogEntry(ts="20260417-064643", screen="color_lcd", saved=False, is_utc=True)


def test_v1_reader_handles_legacy_local_time(tmp_path):
    """Legacy (v1) worklog files have no header, timestamps are local."""
    p = tmp_path / "legacy_worklog"
    p.write_text("20260417-144639 - color_lcd - Saved\n"
                 "20260417-144643 - color_lcd - Skipped (similar to previous)\n")
    entries = list(read_worklog(p))
    assert len(entries) == 2
    assert entries[0].is_utc is False
    assert entries[0].ts == "20260417-144639"  # raw local string preserved


def test_reader_skips_blank_and_comment_lines(tmp_path):
    p = tmp_path / "worklog"
    p.write_text(V2_HEADER + "\n"
                 "\n"
                 "# a comment\n"
                 "20260417-064639 - color_lcd - Saved\n")
    entries = list(read_worklog(p))
    assert len(entries) == 1
```

- [ ] **Step 4.2: Run tests, expect failure**

Run: `pytest tests/test_worklog.py -v`
Expected: ImportError on `memos.worklog`.

- [ ] **Step 4.3: Implement worklog module**

Create `memos/worklog.py`:

```python
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
                # First line is data → legacy v1
                detected = True
            # Skip other comments
            if line.startswith("#"):
                continue
            parts = line.split(" - ", 2)
            if len(parts) < 3:
                continue
            ts, screen, status = parts
            yield WorklogEntry(ts=ts, screen=screen, saved=status.startswith("Saved"), is_utc=is_v2)
```

- [ ] **Step 4.4: Run tests, expect pass**

Run: `pytest tests/test_worklog.py -v`
Expected: 5 passed.

- [ ] **Step 4.5: Update record.py to write UTC worklog entries**

Find the worklog write site (`grep -n 'worklog.write' memos/record.py`). It's around line 313:

```python
worklog.write(f"{timestamp} - {screen_name} - {status}\n")
```

`timestamp` here is local time. Replace with UTC + use the new module:

```python
from memos.worklog import write_entry as worklog_write_entry
from memos.tz_utils import LocalOffset, local_ts_to_utc

# At call site (line ~313, inside the function that has `timestamp`, `screen_name`, `status`):
offset = LocalOffset.from_system()
utc_ts = local_ts_to_utc(timestamp, offset)
saved = (status == "Saved")
worklog_write_entry(worklog_path, utc_ts, screen_name, saved, offset)
```

You will need to find the `worklog_path` variable; in the existing code it's
the file the recorder opens. Also remove the existing manual file handle if
present (the new `write_entry` opens its own).

- [ ] **Step 4.6: Smoke test recorder doesn't crash**

Skip this step if you cannot easily exercise the recorder end-to-end. Instead:
- Run `pytest tests/test_worklog.py -v` (still passes)
- Manually inspect `memos/record.py` for: `from memos.worklog import write_entry as worklog_write_entry`
- Run `python -c "from memos import record"` (no import errors)

- [ ] **Step 4.7: Commit**

```bash
git add memos/worklog.py tests/test_worklog.py memos/record.py
git commit -m "feat(worklog): add v2 UTC format with backwards-compat reader"
```

---

## Task 5: Structured VLM plugin

A FastAPI plugin that mirrors the existing `vlm/` shape. Calls the VLM with
the structured prompt, parses JSON, validates against `ExtractedFields`,
writes `structured_vlm_v1_<modelname>` metadata.

**Files:**
- Create: `memos/plugins/structured_vlm/__init__.py`
- Create: `memos/plugins/structured_vlm/main.py`
- Create: `memos/plugins/structured_vlm/prompt_v1.py`
- Create: `memos/plugins/structured_vlm/prompt_v1.txt`
- Create: `memos/plugins/structured_vlm/requirements.txt`
- Create: `tests/test_plugin_structured_vlm.py`
- Create: `tests/fixtures/screenshots/sample_iterm.webp` (copy 1 webp from real data)
- Create: `tests/fixtures/vlm_responses/iterm_cc_task.json` (canned good response)
- Create: `tests/fixtures/vlm_responses/malformed.json` (canned bad response)
- Modify: `memos/config.py:18` (add `StructuredVLMSettings` after `VLMSettings`)
- Modify: `memos/server.py:1148` (wire the new plugin router)

- [ ] **Step 5.1: Copy prompt asset from POC**

```bash
cp docs/superpowers/experiments/vlm_bench/prompt_v1.txt memos/plugins/structured_vlm/prompt_v1.txt
```

- [ ] **Step 5.2: Copy a real screenshot fixture**

```bash
cp docs/superpowers/experiments/vlm_bench/samples.jsonl /tmp/samples_to_pick.jsonl
# Pick one filepath to copy as fixture; this is a representative iTerm sample
SAMPLE_PATH=$(jq -r 'select(.label=="iterm_cc_task_debug_gear") | .filepath' /tmp/samples_to_pick.jsonl)
cp "$SAMPLE_PATH" tests/fixtures/screenshots/sample_iterm_cc.webp
```

- [ ] **Step 5.3: Create canned VLM response fixtures**

Create `tests/fixtures/vlm_responses/iterm_cc_task.json`:

```json
{
  "primary": {
    "app": "iTerm2",
    "what": "在终端中查看关于 BayesJob 控制器状态卡死问题的调试笔记",
    "title_or_topic": "Debug gear controller blocking issue with bayesjob",
    "workspace": "openbayes-gear-controller"
  },
  "secondary": [],
  "contact": null,
  "url": null,
  "confidence": {"primary": "high", "contact": null, "url": null},
  "notes": "iTerm2 single window with terminal output"
}
```

Create `tests/fixtures/vlm_responses/malformed.json`:

```text
this is not json at all and the model returned garbage
```

- [ ] **Step 5.4: Create prompt_v1.py wrapper**

Create `memos/plugins/structured_vlm/prompt_v1.py`:

```python
"""Versioned prompt asset for structured VLM extraction.

The prompt text lives in prompt_v1.txt as a sibling file so it is easy to
inspect / version-control / diff. The version string is part of the metadata
field name, so prompt changes always get a new field rather than overwriting.
"""
from pathlib import Path

PROMPT_VERSION = "v1"

_THIS_DIR = Path(__file__).parent
PROMPT_TEXT = (_THIS_DIR / "prompt_v1.txt").read_text(encoding="utf-8")
```

- [ ] **Step 5.5: Write failing plugin tests**

Create `tests/fixtures/__init__.py` (empty) and `tests/test_plugin_structured_vlm.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest
import respx
from httpx import Response

from memos.plugins.structured_vlm.main import (
    parse_vlm_response_to_extracted,
    metadata_field_name,
    predict_structured,
)
from memos.extractors.schema import ExtractedFields

FIXTURES = Path(__file__).parent / "fixtures"


def test_metadata_field_name_uses_versioned_id():
    name = metadata_field_name(modelname="qwen3.6-35b")
    assert name == "structured_vlm_v1_qwen3_6_35b"


def test_parse_clean_json_response():
    raw = (FIXTURES / "vlm_responses" / "iterm_cc_task.json").read_text()
    result = parse_vlm_response_to_extracted(raw, modelname="qwen3.6-35b")
    assert isinstance(result, ExtractedFields)
    assert result.extractor == "structured_vlm_v1_qwen3_6_35b"
    assert result.primary.workspace == "openbayes-gear-controller"
    assert result.primary.app == "iTerm2"


def test_parse_strips_markdown_codeblock():
    """If model wraps JSON in ```json ... ```, parser still succeeds."""
    raw = '```json\n{"primary": {"app": "Cursor"}, "confidence": {}}\n```'
    result = parse_vlm_response_to_extracted(raw, modelname="qwen3.6-35b")
    assert result.primary.app == "Cursor"


def test_parse_returns_none_on_unrecoverable_garbage():
    raw = "this is not json at all and contains no recoverable braces"
    result = parse_vlm_response_to_extracted(raw, modelname="qwen3.6-35b")
    assert result is None


@pytest.mark.asyncio
async def test_predict_structured_calls_vlm_and_parses(tmp_path):
    """The full predict_structured path mocks the VLM call and returns a parsed ExtractedFields."""
    img_path = FIXTURES / "screenshots" / "sample_iterm_cc.webp"
    canned_response_text = (FIXTURES / "vlm_responses" / "iterm_cc_task.json").read_text()
    api_envelope = {
        "choices": [{"message": {"content": canned_response_text}}]
    }

    with respx.mock(base_url="https://fake-vlm.test") as mock:
        mock.post("/v1/chat/completions").mock(return_value=Response(200, json=api_envelope))
        result = await predict_structured(
            endpoint="https://fake-vlm.test",
            modelname="qwen3.6-35b",
            img_path=str(img_path),
            token=None,
        )

    assert result is not None
    assert result.primary.workspace == "openbayes-gear-controller"
```

- [ ] **Step 5.6: Run tests, expect failure**

Run: `pytest tests/test_plugin_structured_vlm.py -v`
Expected: ImportError on `memos.plugins.structured_vlm.main`.

- [ ] **Step 5.7: Implement the plugin module**

Create `memos/plugins/structured_vlm/__init__.py` (empty).

Create `memos/plugins/structured_vlm/requirements.txt`:

```text
httpx
fastapi
pydantic>=2.0
```

Create `memos/plugins/structured_vlm/main.py`:

```python
"""Structured VLM plugin for Pensieve.

Calls a VLM endpoint with the v1 structured prompt and stores the parsed
result as `structured_vlm_v1_<modelname>` metadata on each entity.

Mirrors the existing `vlm/` plugin shape (FastAPI app, init_plugin, POST handler).
"""
from __future__ import annotations
import asyncio
import base64
import io
import json
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from PIL import Image

from memos.extractors.schema import ExtractedFields
from memos.plugins.structured_vlm.prompt_v1 import PROMPT_TEXT, PROMPT_VERSION
from memos.schemas import Entity, MetadataType

logger = logging.getLogger(__name__)
PLUGIN_NAME = "structured_vlm"

router = APIRouter(tags=[PLUGIN_NAME], responses={404: {"description": "Not found"}})

# Module-level config, populated by init_plugin()
modelname: Optional[str] = None
endpoint: Optional[str] = None
token = None
concurrency: int = 4
force_jpeg: bool = True
max_tokens: int = 2048
disable_thinking: bool = True
semaphore: Optional[asyncio.Semaphore] = None


def metadata_field_name(modelname: str) -> str:
    """Versioned metadata key per (prompt_version, model). Same model → same key."""
    safe_model = re.sub(r"[^A-Za-z0-9]", "_", modelname).lower()
    return f"structured_vlm_{PROMPT_VERSION}_{safe_model}"


def _image_to_base64(img_path: str, max_width: int = 1600, quality: int = 85) -> Optional[str]:
    """Open, downscale if needed, return base64 JPEG."""
    try:
        img = Image.open(img_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logger.warning(f"Failed to load image {img_path}: {e}")
        return None


def _parse_json_loose(text: str) -> Optional[dict]:
    """Try direct parse, then markdown-stripped, then first {..} block."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def parse_vlm_response_to_extracted(raw_text: str, modelname: str) -> Optional[ExtractedFields]:
    """Parse the VLM's text response into an ExtractedFields. Returns None if unrecoverable."""
    parsed = _parse_json_loose(raw_text)
    if not parsed:
        return None
    try:
        return ExtractedFields(extractor=metadata_field_name(modelname), **parsed)
    except Exception as e:
        logger.warning(f"VLM JSON does not match ExtractedFields schema: {e}; raw: {raw_text[:200]}")
        return None


async def predict_structured(
    endpoint: str, modelname: str, img_path: str,
    token: Optional[object] = None, max_tokens: int = 2048,
    disable_thinking: bool = True,
) -> Optional[ExtractedFields]:
    """Call VLM endpoint, return ExtractedFields or None on failure."""
    img_b64 = _image_to_base64(img_path)
    if not img_b64:
        return None
    request_data = {
        "model": modelname,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": PROMPT_TEXT},
            ],
        }],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.1,
        "top_p": 0.8,
    }
    if disable_thinking:
        request_data["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    headers = {"Content-Type": "application/json"}
    if token is not None:
        # Token may be a SecretStr (pydantic) or plain str
        token_str = token.get_secret_value() if hasattr(token, "get_secret_value") else str(token)
        if token_str:
            headers["Authorization"] = f"Bearer {token_str}"

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"{endpoint.rstrip('/')}/v1/chat/completions",
                headers=headers, json=request_data, timeout=180.0,
            )
            r.raise_for_status()
            data = r.json()
            raw_text = data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"VLM call failed for {img_path}: {e}")
            return None

    return parse_vlm_response_to_extracted(raw_text, modelname)


@router.get("/")
async def read_root():
    return {"healthy": True, "plugin": PLUGIN_NAME, "model": modelname,
            "prompt_version": PROMPT_VERSION}


@router.post("", include_in_schema=False)
@router.post("/")
async def handle_entity(entity: Entity, request: Request):
    """Plugin webhook: process entity, write metadata back."""
    if entity.file_type_group != "image":
        return {}
    field = metadata_field_name(modelname)
    existing = entity.get_metadata_by_key(field)
    if existing and existing.value and existing.value.strip():
        logger.info(f"Skip {entity.filepath}: already has {field}")
        return {field: existing.value}

    location_url = request.headers.get("Location")
    if not location_url:
        raise HTTPException(status_code=400, detail="Location header is missing")

    async with semaphore:
        result = await predict_structured(
            endpoint=endpoint, modelname=modelname,
            img_path=entity.filepath, token=token,
            max_tokens=max_tokens, disable_thinking=disable_thinking,
        )

    if result is None:
        logger.info(f"No structured VLM result for {entity.filepath}")
        return {field: ""}

    value = result.model_dump_json()
    patch_url = f"{location_url}/metadata"
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            patch_url,
            json={"metadata_entries": [{
                "key": field, "value": value,
                "source": PLUGIN_NAME, "data_type": MetadataType.TEXT_DATA.value,
            }]},
            timeout=30,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to patch metadata")
    return {field: value}


def init_plugin(config) -> None:
    global modelname, endpoint, token, concurrency, force_jpeg, max_tokens, disable_thinking, semaphore
    modelname = config.modelname
    endpoint = config.endpoint
    token = config.token
    concurrency = config.concurrency
    force_jpeg = config.force_jpeg
    max_tokens = config.max_tokens
    disable_thinking = config.disable_thinking
    semaphore = asyncio.Semaphore(concurrency)
    logger.info(f"structured_vlm plugin initialized: model={modelname}, "
                f"prompt={PROMPT_VERSION}, max_tokens={max_tokens}, "
                f"disable_thinking={disable_thinking}")
```

- [ ] **Step 5.8: Add config schema**

Edit `memos/config.py` and add after the existing `VLMSettings` class (~line 28):

```python
class StructuredVLMSettings(BaseModel):
    """Settings for the structured VLM plugin (Layer 1 extractor).

    The prompt is asset-versioned in code (memos/plugins/structured_vlm/prompt_v1.txt).
    Only the model + endpoint + tuning live here.

    Defaults mirror VLMSettings — the typical setup has ollama (or compatible)
    running on localhost:11434 with minicpm-v. Users override modelname/endpoint
    in config.yaml to point at a different VLM.
    """
    modelname: str = "minicpm-v"
    endpoint: str = "http://localhost:11434"
    token: SecretStr = SecretStr("")
    concurrency: int = 8
    force_jpeg: bool = True
    # max_tokens must be high enough for reasoning models (e.g., 16000 for Kimi K2.6)
    max_tokens: int = 2048
    # Disable thinking mode for vLLM/qwen endpoints; OpenRouter/OpenAI ignore this
    disable_thinking: bool = True
    enabled: bool = True
```

Then in the top-level `Settings` class (~line 112), add the field next to `vlm`:

```python
    vlm: VLMSettings = VLMSettings()
    structured_vlm: StructuredVLMSettings = StructuredVLMSettings()
```

- [ ] **Step 5.9: Wire plugin router into server**

Edit `memos/server.py` around line 1148 (after the VLM init block). Add:

```python
    # Only add structured VLM plugin router if enabled
    if settings.structured_vlm.enabled:
        from memos.plugins.structured_vlm import main as structured_vlm_main
        structured_vlm_main.init_plugin(settings.structured_vlm)
        api_router.include_router(structured_vlm_main.router, prefix="/plugins/structured_vlm")
        logging.info("structured_vlm plugin initialized and router added")
    else:
        logging.info("structured_vlm plugin disabled")
```

- [ ] **Step 5.10: Run tests, expect pass**

Run: `pytest tests/test_plugin_structured_vlm.py -v`
Expected: 5 passed.

- [ ] **Step 5.11: Verify server still imports**

Run: `python -c "from memos import server"`
Expected: no error.

- [ ] **Step 5.12: Commit**

```bash
git add memos/plugins/structured_vlm tests/test_plugin_structured_vlm.py tests/fixtures \
        memos/config.py memos/server.py
git commit -m "feat(plugin): add structured_vlm plugin with prompt v1"
```

---

## Task 6: 30-day backfill CLI command

A typer command that finds entities in a date range without
`structured_vlm_v1_<model>` metadata, calls the plugin webhook for each,
and reports progress. Idempotent (rerun = skip processed).

**Files:**
- Create: `memos/cmds/backfill.py`
- Create: `tests/test_cmd_backfill.py`
- Modify: `memos/cmds/__init__.py` (or wherever the typer app composition lives)

- [ ] **Step 6.1: Locate typer app composition**

Run: `grep -rn 'typer.Typer\|add_typer' memos/cmds/ memos/__main__.py 2>/dev/null`
Note the file where `app = typer.Typer()` is created and sub-apps are mounted.

- [ ] **Step 6.2: Write failing backfill test**

Create `tests/test_cmd_backfill.py`:

```python
import json
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from memos.cmds.backfill import (
    list_unprocessed_entity_ids,
    process_one_entity,
    run_backfill,
)


@pytest.mark.asyncio
async def test_list_unprocessed_filters_already_processed():
    """Entities that already have the target metadata field are excluded."""
    # Two entities exist; entity 1 already has metadata, entity 2 does not.
    fake_conn = MagicMock()
    fake_cur = MagicMock()
    fake_cur.fetchall.return_value = [(2,)]  # SQL returns only entity 2
    fake_conn.cursor.return_value.__enter__.return_value = fake_cur
    with patch("memos.cmds.backfill._open_conn", return_value=fake_conn):
        ids = list(list_unprocessed_entity_ids(
            field="structured_vlm_v1_qwen3_6_35b",
            utc_start="20260321-160000", utc_end="20260420-160000",
        ))
    assert ids == [2]
    # Verify the SQL filtered correctly (loose check on text)
    sql = fake_cur.execute.call_args[0][0]
    assert "structured_vlm_v1_qwen3_6_35b" in sql
    assert "NOT EXISTS" in sql.upper() or "LEFT JOIN" in sql.upper()


@pytest.mark.asyncio
async def test_process_one_entity_calls_plugin_webhook():
    """process_one_entity POSTs the entity to the plugin webhook URL."""
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=MagicMock(status_code=200))

    await process_one_entity(
        client=fake_client,
        plugin_url="http://localhost:8839/api/plugins/structured_vlm/",
        entity_url="http://localhost:8839/api/libraries/1/entities/42",
    )

    fake_client.post.assert_awaited_once()
    args, kwargs = fake_client.post.call_args
    # Plugin webhook receives the entity URL via Location header
    assert kwargs["headers"]["Location"].endswith("/entities/42")


@pytest.mark.asyncio
async def test_run_backfill_processes_each_entity_once():
    with patch("memos.cmds.backfill.list_unprocessed_entity_ids", return_value=[10, 11, 12]), \
         patch("memos.cmds.backfill.process_one_entity", new=AsyncMock()) as proc:
        await run_backfill(
            field="structured_vlm_v1_qwen3_6_35b",
            utc_start="20260321-160000", utc_end="20260420-160000",
            base_url="http://localhost:8839",
            library_id=1,
            concurrency=2,
        )
    assert proc.await_count == 3
```

- [ ] **Step 6.3: Run test, expect failure**

Run: `pytest tests/test_cmd_backfill.py -v`
Expected: ImportError on `memos.cmds.backfill`.

- [ ] **Step 6.4: Implement backfill module**

Create `memos/cmds/backfill.py`:

```python
"""Backfill CLI commands. Currently: structured_vlm extractor.

Usage:
  memos backfill structured-vlm --days 30 --concurrency 8
"""
from __future__ import annotations
import asyncio
import logging
from typing import Iterator, Optional

import httpx
import typer

from memos.config import settings
from memos.tz_utils import LocalOffset, local_date_to_utc_range
from memos.plugins.structured_vlm.main import metadata_field_name as svlm_field_name

logger = logging.getLogger(__name__)

backfill_app = typer.Typer(help="Backfill commands for derived metadata.")


def _open_conn():
    """Open a psycopg2 connection. Imported lazily so test environments without
    psycopg2 still load the module."""
    import psycopg2
    # Parse the SQLAlchemy URL into psycopg2 args
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url[len("postgresql://"):]
    user_pw, host_db = url.split("@", 1)
    user, pw = user_pw.split(":", 1)
    host_port, db = host_db.split("/", 1)
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host, port = host_port, "5432"
    return psycopg2.connect(host=host, port=port, user=user, password=pw, dbname=db)


def list_unprocessed_entity_ids(field: str, utc_start: str, utc_end: str) -> Iterator[int]:
    """Yield entity IDs in [utc_start, utc_end) that do NOT yet have the given metadata field."""
    conn = _open_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT e.id FROM entities e
                JOIN metadata_entries m_ts ON m_ts.entity_id = e.id AND m_ts.key = 'timestamp'
                WHERE m_ts.value >= %s AND m_ts.value < %s
                  AND NOT EXISTS (
                    SELECT 1 FROM metadata_entries m
                    WHERE m.entity_id = e.id AND m.key = %s
                  )
                ORDER BY m_ts.value;
            """, (utc_start, utc_end, field))
            for (eid,) in cur.fetchall():
                yield eid
    finally:
        conn.close()


async def process_one_entity(client, plugin_url: str, entity_url: str) -> None:
    """POST to the plugin webhook with Location header pointing at the entity."""
    try:
        r = await client.post(plugin_url,
                              headers={"Location": entity_url},
                              json={},  # plugin loads entity via location
                              timeout=300.0)
        if r.status_code != 200:
            logger.warning(f"Plugin returned {r.status_code} for {entity_url}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"Backfill failed for {entity_url}: {e}")


async def run_backfill(field: str, utc_start: str, utc_end: str,
                       base_url: str, library_id: int, concurrency: int) -> None:
    plugin_url = f"{base_url}/api/plugins/structured_vlm/"
    ids = list(list_unprocessed_entity_ids(field=field, utc_start=utc_start, utc_end=utc_end))
    total = len(ids)
    print(f"To process: {total} entities. Concurrency: {concurrency}.")
    if total == 0:
        return
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(eid: int):
        nonlocal done
        entity_url = f"{base_url}/api/libraries/{library_id}/entities/{eid}"
        async with sem:
            await process_one_entity(client, plugin_url, entity_url)
            done += 1
            if done % 50 == 0 or done == total:
                print(f"  [{done}/{total}] processed")

    async with httpx.AsyncClient() as client:
        await asyncio.gather(*(one(eid) for eid in ids))
    print(f"Done: {done}/{total} processed.")


@backfill_app.command("structured-vlm")
def cmd_structured_vlm(
    days: int = typer.Option(30, "--days", help="How many days back from today (local) to backfill."),
    concurrency: int = typer.Option(4, "--concurrency", help="Concurrent webhook requests."),
    library_id: int = typer.Option(1, "--lib", help="Library ID for entity URL composition."),
    base_url: Optional[str] = typer.Option(None, "--base-url",
        help=f"Server base URL (defaults to settings.server_endpoint)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print count of unprocessed and exit."),
):
    """Run structured_vlm extraction on screenshots from the last N local days."""
    from datetime import datetime, timedelta
    offset = LocalOffset.from_system()
    today_local = datetime.now()
    end_local = today_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start_local = end_local - timedelta(days=days)
    utc_start, _ = local_date_to_utc_range(start_local.strftime("%Y%m%d"), offset)
    _, utc_end = local_date_to_utc_range((end_local - timedelta(days=1)).strftime("%Y%m%d"), offset)

    field = svlm_field_name(modelname=settings.structured_vlm.modelname)
    base = base_url or settings.server_endpoint

    print(f"Backfill: field={field}, UTC range [{utc_start}, {utc_end}), base_url={base}")
    if dry_run:
        ids = list(list_unprocessed_entity_ids(field=field, utc_start=utc_start, utc_end=utc_end))
        print(f"DRY RUN: {len(ids)} entities would be processed.")
        return

    asyncio.run(run_backfill(field=field, utc_start=utc_start, utc_end=utc_end,
                             base_url=base, library_id=library_id, concurrency=concurrency))
```

- [ ] **Step 6.5: Mount backfill_app on the main typer app**

Find the typer composition (Step 6.1 located it). Add:

```python
from memos.cmds.backfill import backfill_app
app.add_typer(backfill_app, name="backfill")
```

- [ ] **Step 6.6: Run tests, expect pass**

Run: `pytest tests/test_cmd_backfill.py -v`
Expected: 3 passed.

- [ ] **Step 6.7: Smoke test the CLI command**

Run: `memos backfill structured-vlm --days 30 --dry-run`
Expected: prints `DRY RUN: <N> entities would be processed.` (likely several thousand for an active 30-day window).

- [ ] **Step 6.8: Commit**

```bash
git add memos/cmds/backfill.py tests/test_cmd_backfill.py memos/cmds/__init__.py
git commit -m "feat(cmd): add backfill structured-vlm command"
```

---

## Task 7: Run the actual 30-day backfill and verify

Now actually run the backfill against the real DB and validate results match
the POC bench (same prompt, same model, same images → same outputs within
sampling noise).

**Files:** none new; this task validates production data.

- [ ] **Step 7.1: Enable structured_vlm in user config**

Edit `~/.memos/config.yaml`. Add the section:

```yaml
structured_vlm:
  enabled: true
  modelname: qwen3.6-35b
  endpoint: https://aisensiy-vycpv1a7wiky.serv-c1.openbayes.net
  token: sk-4i1rvtly17cfx805nva8q6ibfd5qvaar
  concurrency: 8
  force_jpeg: true
  max_tokens: 2048
  disable_thinking: true
```

- [ ] **Step 7.2: Restart the Pensieve server**

Restart however you currently run it (e.g., `~/.memos/launch.sh restart` or
`memos serve`). Confirm the structured_vlm plugin is initialized:

```bash
grep -i structured_vlm ~/.memos/logs/memos.log | head -3
```
Expected: line "structured_vlm plugin initialized and router added".

- [ ] **Step 7.3: Smoke test plugin endpoint**

```bash
curl -s http://localhost:8839/api/plugins/structured_vlm/ | jq .
```
Expected: `{"healthy": true, "plugin": "structured_vlm", "model": "qwen3.6-35b", "prompt_version": "v1"}`

- [ ] **Step 7.4: Backfill the most recent 1 day first (canary)**

```bash
memos backfill structured-vlm --days 1 --concurrency 4
```
Expected: `[N/N] processed.` Usually ~2-5k entities; should complete in 20-40 minutes.

Verify a few entities have the new metadata:

```bash
PGPASSWORD=mysecretpassword psql -h localhost -U postgres -d postgres -c \
  "SELECT count(*) FROM metadata_entries WHERE key = 'structured_vlm_v1_qwen3_6_35b';"
```

- [ ] **Step 7.5: Cross-check 3 sample entities against POC bench**

Pick 3 entity IDs from `docs/superpowers/experiments/vlm_bench/samples.jsonl`
that fall in the last day. For each, compare backfill output to POC output:

```bash
PGPASSWORD=mysecretpassword psql -h localhost -U postgres -d postgres -t -c \
  "SELECT value FROM metadata_entries WHERE entity_id = <ID> \
   AND key = 'structured_vlm_v1_qwen3_6_35b';" | jq .
```

Compare with `docs/superpowers/experiments/vlm_bench/results/qwen3.6-35b.jsonl`.
Expect: `primary.workspace`, `primary.app`, `primary.title_or_topic` fields
match within VLM sampling noise. Document any structural mismatch (not just
phrasing differences) as an issue.

- [ ] **Step 7.6: Run the full 30-day backfill**

```bash
memos backfill structured-vlm --days 30 --concurrency 8
```
Expected runtime: 8-12 hours (per spec §10.1). Run in a long-lived shell or
under `nohup`. Check progress periodically:

```bash
PGPASSWORD=mysecretpassword psql -h localhost -U postgres -d postgres -c \
  "SELECT count(*) FROM metadata_entries WHERE key = 'structured_vlm_v1_qwen3_6_35b';"
```

- [ ] **Step 7.7: Final validation queries**

After completion, sanity check:

```bash
# Count of entities in the last 30 days that have the new metadata
PGPASSWORD=mysecretpassword psql -h localhost -U postgres -d postgres -c "
  WITH em AS (
    SELECT e.id, MAX(CASE WHEN m.key='timestamp' THEN m.value END) AS ts
    FROM entities e JOIN metadata_entries m ON m.entity_id=e.id
    WHERE m.key='timestamp' GROUP BY e.id
  )
  SELECT count(*) FROM em
  JOIN metadata_entries svlm ON svlm.entity_id=em.id AND svlm.key='structured_vlm_v1_qwen3_6_35b'
  WHERE em.ts >= '20260322-160000';
"
```

Expected: matches the count from Step 6.7's `--dry-run` (within a small margin
for failed individual VLM calls).

- [ ] **Step 7.8: Spot-check workspace fill rate**

Run a quick aggregation to confirm spec-§10.2 evaluation gate ("workspace
fill-rate ~70%+"):

```bash
PGPASSWORD=mysecretpassword psql -h localhost -U postgres -d postgres -c "
  SELECT
    count(*) FILTER (WHERE value::jsonb->'primary'->>'workspace' IS NOT NULL) AS with_ws,
    count(*) AS total
  FROM metadata_entries
  WHERE key='structured_vlm_v1_qwen3_6_35b';
"
```

Expected: `with_ws / total >= 0.5` (50%+ acceptable for a real-world full
day, vs the 75% on the curated POC sample). If significantly lower than 50%,
investigate prompt drift or model issues before declaring success.

- [ ] **Step 7.9: Document the run**

Append to `docs/superpowers/experiments/backfill_log.md` (create if absent):

```markdown
# Backfill log

## 2026-04-XX: structured_vlm_v1_qwen3_6_35b — last 30 days
- Entities processed: <count>
- Workspace fill rate: <pct>
- Avg time/entity: <sec>
- Issues found: <none | list>
```

- [ ] **Step 7.10: Commit any spec/doc updates**

```bash
git add docs/superpowers/experiments/backfill_log.md
git commit -m "docs(backfill): record 30-day structured_vlm backfill results"
```

---

## Spec coverage check

| Spec section | Implemented in |
|---|---|
| §4 Timezone strategy (worklog UTC, local_tz_offset record) | Task 1, Task 4 |
| §5.1 Title regex extractor | Task 2, Task 3 |
| §5.2 Versioned prompt asset | Task 5 (prompt_v1.txt + prompt_v1.py) |
| §5.3 Plugin extractor pattern | Task 5 |
| §5.4 VLM as visual truth (overrides recorder) | Schema in Task 2; merge logic deferred to Plan 2 (Layer 2 access time) |
| §10.1 Phase 1 last-30-days backfill | Task 6, Task 7 |
| §10.2 Evaluation gate | Task 7 (Step 7.8 spot-check) |
| §10.4 Prompt versioning | Task 5 (`structured_vlm_<version>_<model>` field name) |

**Out of scope for Plan 1** (deferred to later plans, per spec §0):
- Layer 2 aggregation (TaskSession/AttentionMoment/AttentionTick) — Plan 2
- Retrieval API surfaces — Plan 3
- UI views — Plan 3 / Plan 4
- §9 recorder data integrity bugs — separate hotfix tickets
