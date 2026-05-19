# Processing Status Pill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the in-repo mock with the real processing-status pill: a backend aggregate endpoint, four CRUD helpers, watch-state utilities driven by the existing PID file, and a self-contained React component that polls every 30 seconds and renders the panel approved during brainstorm.

**Architecture:** Add a new GET `/api/libraries/{id}/processing-status` route registered on `api_router` with a 10s TTL cache (mirroring the `_collection_size_cache` pattern in `server.py:914`). The route composes four new pure crud helpers (`count_entities_in_window`, `count_entities_fully_processed_in_window`, `count_unprocessed`, `get_oldest_unprocessed_created_at`) and three watch predicates extracted into a new shared module `memos/utils/watch_state.py` (`is_alive` from PID file, `is_on_battery` lifted out of `cmds/library.py`, `is_within_idle_window` lifted from `WatchHandler`). Frontend `useProcessingStatus(libraryId)` hook polls every 30s with `refetchOnWindowFocus`; the existing `<ProcessingStatusPill>` swaps mock prop for the hook and renders nothing when no `kind == record` library exists.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0, psutil, pytest. React 18, TanStack Query v5, TanStack Router, shadcn/ui (radix popover), vitest.

**Reference spec:** `docs/superpowers/specs/2026-05-19-processing-status-pill-design.md`

---

## File Structure

**Backend (new):**
- `memos/utils/__init__.py` — empty package marker (already present? verify in Task 1)
- `memos/utils/watch_state.py` — three predicates: `is_alive`, `is_on_battery`, `is_within_idle_window`
- `tests/test_watch_state.py` — unit tests for the three predicates
- `tests/test_processing_status_crud.py` — unit tests for the four CRUD helpers (in-memory SQLite with synthetic plugin / status rows)
- `tests/test_processing_status_route.py` — TestClient integration: response shape, error paths, cache behavior

**Backend (modified):**
- `memos/cmds/library.py` — replace inline `is_on_battery` (line 735) and inline `is_within_idle_window` (method on `WatchHandler`) with imports from `memos/utils/watch_state.py`
- `memos/crud.py` — append four new helpers
- `memos/schemas.py` — add `ProcessingStatusResponse` and its three sub-models
- `memos/server.py` — register the new route on `api_router`; add `_processing_status_cache` next to `_collection_size_cache`

**Frontend (new):**
- `web/src/lib/api/processing-status.ts` — `useProcessingStatus(libraryId)` react-query hook + `ProcessingStatus` response type alias
- `web/src/lib/processing-status.test.ts` — pure-function tests for `pillState` and `headlineReason`
- `web/src/components/common/ProcessingStatusPill.test.tsx` — render tests across the six headline states

**Frontend (modified):**
- `web/src/lib/processing-status.ts` — strip `MOCK_PAYLOADS`, `MOCK_ORDER`, `MOCK_LABELS`; keep the type, `pillState`, `headlineReason`, `humanizeAge`, `humanizeComputedAt`
- `web/src/components/common/ProcessingStatusPill.tsx` — switch from `status` prop to self-resolving from `useLibraries()` + `useProcessingStatus()`; render null when no record-library
- `web/src/routes/index.tsx` — remove `<select>` dev picker, import path stays the same, render `<ProcessingStatusPill />` with no props

**i18n (final task):**
- `web/src/locales/en.json` and `web/src/locales/zh.json` — `status.*` namespace

---

## Task 1: Watch state utilities — write failing tests

**Files:**
- Test: `tests/test_watch_state.py` (create)

- [ ] **Step 1: Create the test file**

```python
"""Tests for memos.utils.watch_state predicates."""
import os
from unittest.mock import patch

import pytest

from memos.utils import watch_state


class TestIsAlive:
    def test_returns_false_when_no_pid_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: tmp_path / "missing.pid")
        assert watch_state.is_alive() is False

    def test_returns_false_when_pid_file_empty(self, tmp_path, monkeypatch):
        pid_path = tmp_path / "watch.pid"
        pid_path.write_text("")
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: pid_path)
        assert watch_state.is_alive() is False

    def test_returns_false_for_dead_pid(self, tmp_path, monkeypatch):
        pid_path = tmp_path / "watch.pid"
        pid_path.write_text("999999")
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: pid_path)
        assert watch_state.is_alive() is False

    def test_returns_true_for_own_process(self, tmp_path, monkeypatch):
        pid_path = tmp_path / "watch.pid"
        pid_path.write_text(str(os.getpid()))
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: pid_path)
        assert watch_state.is_alive() is True


class TestIsOnBattery:
    def test_returns_false_when_no_battery(self):
        with patch("memos.utils.watch_state.psutil.sensors_battery", return_value=None):
            assert watch_state.is_on_battery() is False

    def test_returns_true_when_unplugged(self):
        class FakeBattery:
            power_plugged = False
        with patch("memos.utils.watch_state.psutil.sensors_battery", return_value=FakeBattery()):
            assert watch_state.is_on_battery() is True

    def test_returns_false_when_plugged(self):
        class FakeBattery:
            power_plugged = True
        with patch("memos.utils.watch_state.psutil.sensors_battery", return_value=FakeBattery()):
            assert watch_state.is_on_battery() is False


class TestIsWithinIdleWindow:
    def test_same_day_window_inside(self):
        # config: 08:00-18:00, current = 12:00
        assert watch_state.is_within_idle_window(("08:00", "18:00"), now_hhmm="12:00") is True

    def test_same_day_window_outside(self):
        assert watch_state.is_within_idle_window(("08:00", "18:00"), now_hhmm="20:00") is False

    def test_crosses_midnight_inside_after_start(self):
        # 22:00-06:00, current 23:00 → inside
        assert watch_state.is_within_idle_window(("22:00", "06:00"), now_hhmm="23:00") is True

    def test_crosses_midnight_inside_before_end(self):
        # 22:00-06:00, current 04:00 → inside
        assert watch_state.is_within_idle_window(("22:00", "06:00"), now_hhmm="04:00") is True

    def test_crosses_midnight_outside(self):
        # 22:00-06:00, current 12:00 → outside
        assert watch_state.is_within_idle_window(("22:00", "06:00"), now_hhmm="12:00") is False

    def test_full_day_window(self):
        # 00:00-23:59 always inside
        assert watch_state.is_within_idle_window(("00:00", "23:59"), now_hhmm="03:14") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_watch_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'memos.utils.watch_state'`

---

## Task 2: Watch state utilities — implement

**Files:**
- Create: `memos/utils/__init__.py` (if it doesn't already exist)
- Create: `memos/utils/watch_state.py`

- [ ] **Step 1: Confirm `memos/utils/` package exists or create it**

Run: `ls memos/utils/__init__.py 2>/dev/null && echo "exists" || touch memos/utils/__init__.py`

(If the file did not exist and was just created, it is an empty package marker — no further content needed.)

- [ ] **Step 2: Create the module**

```python
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
    # Crosses midnight.
    return now >= start or now <= end


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_watch_state.py -v`
Expected: PASS — all 11 tests green.

- [ ] **Step 4: Commit**

```bash
git add memos/utils/__init__.py memos/utils/watch_state.py tests/test_watch_state.py
git commit -m "utils(watch-state): factor is_alive/on_battery/in_idle_window from cmds.library"
```

---

## Task 3: Refactor cmds/library.py to import from watch_state

**Files:**
- Modify: `memos/cmds/library.py:735` (replace local `is_on_battery`) and the `WatchHandler.is_within_process_interval` method body (around line 817)

- [ ] **Step 1: Replace the local `is_on_battery`**

In `memos/cmds/library.py`, find:

```python
def is_on_battery():
    # ... existing body (uses psutil.sensors_battery) ...
```

Replace the whole function with a re-export to keep call sites working without churn:

```python
from memos.utils.watch_state import is_on_battery  # re-export, see memos/utils/watch_state.py
```

- [ ] **Step 2: Reuse the window helper from `WatchHandler.is_within_process_interval`**

The current method (around `library.py:817`) computes inside vs outside vs cross-midnight inline. Replace the method body with a delegation:

```python
def is_within_process_interval(self) -> bool:
    """Check if current time is within the idle process interval"""
    from memos.utils.watch_state import is_within_idle_window
    return is_within_idle_window(
        (
            settings.watch.idle_process_interval[0],
            settings.watch.idle_process_interval[1],
        )
    )
```

This removes the `idle_process_start` / `idle_process_end` / `last_in_process_window` time-arithmetic branches at the top of `__init__` (around `library.py:795-808`) since the helper does the work. Leave the `last_in_process_window` cache field alone if it's used elsewhere; only the parse-time-strings logic moves.

- [ ] **Step 3: Run the existing test suite to make sure nothing in cmds.library broke**

Run: `pytest tests/ -v --no-header 2>&1 | tail -40`
Expected: All previously-passing tests still pass. If any test imports `is_on_battery` from `memos.cmds.library`, the re-export from Step 1 keeps it working.

- [ ] **Step 4: Commit**

```bash
git add memos/cmds/library.py
git commit -m "cmds(library): use utils.watch_state for battery/idle-window checks"
```

---

## Task 4: CRUD — `count_entities_in_window` test

**Files:**
- Test: `tests/test_processing_status_crud.py` (create)

- [ ] **Step 1: Write the failing test plus shared fixtures**

```python
"""Tests for the processing-status crud helpers."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memos import crud
from memos.models import (
    Base,
    EntityModel,
    EntityPluginStatusModel,
    FolderModel,
    LibraryModel,
    LibraryPluginModel,
    PluginModel,
)
from memos.schemas import LibraryKind


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


def _utc(now_offset_minutes: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=now_offset_minutes)


def _seed(session, *, library_kind=LibraryKind.RECORD, n_plugins=2, entity_specs=()):
    """Seed one library with `n_plugins` bound plugins and entities with the
    plugin-status pattern specified by entity_specs.

    Each entity_spec is a tuple (created_minutes_ago, plugins_done_count).
    Returns (library_id, [entity_ids]).
    """
    lib = LibraryModel(name="test", kind=library_kind)
    session.add(lib)
    session.flush()
    folder = FolderModel(
        library_id=lib.id,
        path="/tmp",
        last_modified_at=datetime.now(timezone.utc),
    )
    session.add(folder)
    session.flush()
    plugins = []
    for i in range(n_plugins):
        p = PluginModel(name=f"plugin-{i}", webhook_url=f"/p{i}")
        session.add(p)
        session.flush()
        session.add(LibraryPluginModel(library_id=lib.id, plugin_id=p.id))
        plugins.append(p)
    session.flush()
    entity_ids = []
    for created_minutes_ago, plugins_done in entity_specs:
        created_at = _utc(-created_minutes_ago)
        ent = EntityModel(
            filepath=f"/tmp/e-{created_minutes_ago}-{plugins_done}.png",
            filename=f"e-{created_minutes_ago}-{plugins_done}.png",
            size=1,
            file_created_at=created_at,
            file_last_modified_at=created_at,
            file_type="image/png",
            file_type_group="image",
            library_id=lib.id,
            folder_id=folder.id,
            created_at=created_at,
            updated_at=created_at,
            last_scan_at=created_at,
        )
        session.add(ent)
        session.flush()
        for p in plugins[:plugins_done]:
            session.add(
                EntityPluginStatusModel(entity_id=ent.id, plugin_id=p.id)
            )
        entity_ids.append(ent.id)
    session.commit()
    return lib.id, entity_ids


def test_count_entities_in_window_counts_inside_window_only(session):
    # window = 60 minutes; seed 3 inside, 2 outside
    lib_id, _ = _seed(
        session,
        entity_specs=[
            (5, 2),   # 5 min ago, in
            (30, 0),  # 30 min ago, in
            (45, 1),  # 45 min ago, in
            (90, 2),  # 90 min ago, OUT
            (120, 0), # 120 min ago, OUT
        ],
    )
    n = crud.count_entities_in_window(lib_id, window_hours=1, db=session)
    assert n == 3


def test_count_entities_in_window_empty_returns_zero(session):
    lib_id, _ = _seed(session, entity_specs=[])
    assert crud.count_entities_in_window(lib_id, window_hours=24, db=session) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_processing_status_crud.py::test_count_entities_in_window_counts_inside_window_only -v`
Expected: FAIL — `AttributeError: module 'memos.crud' has no attribute 'count_entities_in_window'`

---

## Task 5: CRUD — `count_entities_in_window` implement

**Files:**
- Modify: `memos/crud.py` (append at end)

- [ ] **Step 1: Add the helper**

Append to `memos/crud.py`:

```python
def count_entities_in_window(library_id: int, window_hours: int, db: Session) -> int:
    """Count entities created in the rolling window for one library."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    return (
        db.query(EntityModel)
        .filter(EntityModel.library_id == library_id)
        .filter(EntityModel.created_at >= cutoff)
        .count()
    )
```

Make sure the imports at the top of `crud.py` include `datetime`, `timedelta`, and `timezone` from `datetime`. They should already be present; if not, add them.

- [ ] **Step 2: Run the two count_in_window tests to verify they pass**

Run: `pytest tests/test_processing_status_crud.py -k count_entities_in_window -v`
Expected: PASS — 2 tests green.

- [ ] **Step 3: Commit (with the test file)**

```bash
git add memos/crud.py tests/test_processing_status_crud.py
git commit -m "crud: count_entities_in_window for processing-status coverage denominator"
```

---

## Task 6: CRUD — `count_entities_fully_processed_in_window` test + implement

**Files:**
- Modify: `tests/test_processing_status_crud.py` (append tests)
- Modify: `memos/crud.py` (append helper)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_processing_status_crud.py`:

```python
def test_count_fully_processed_only_counts_all_plugins_done(session):
    # 2 plugins. Seed entities where:
    # - inside window, all plugins done → counts
    # - inside window, 1/2 plugins → does NOT count
    # - inside window, 0/2 plugins → does NOT count
    # - outside window, all plugins done → does NOT count
    lib_id, _ = _seed(
        session,
        n_plugins=2,
        entity_specs=[
            (5, 2),   # in, fully processed
            (10, 1),  # in, partial
            (20, 0),  # in, none
            (30, 2),  # in, fully processed
            (90, 2),  # OUT
        ],
    )
    n = crud.count_entities_fully_processed_in_window(lib_id, window_hours=1, db=session)
    assert n == 2


def test_count_fully_processed_returns_zero_when_no_plugins_bound(session):
    # Edge: library has 0 plugins bound. Every entity is trivially "fully
    # processed" (0/0), and we return 0 to avoid divide-by-zero confusion
    # downstream.
    lib_id, _ = _seed(
        session,
        n_plugins=0,
        entity_specs=[(5, 0), (10, 0)],
    )
    assert crud.count_entities_fully_processed_in_window(lib_id, window_hours=1, db=session) == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_processing_status_crud.py -k fully_processed -v`
Expected: FAIL — `AttributeError: count_entities_fully_processed_in_window`

- [ ] **Step 3: Implement**

Append to `memos/crud.py`:

```python
def count_entities_fully_processed_in_window(
    library_id: int, window_hours: int, db: Session
) -> int:
    """Count entities in the window that have an entity_plugin_status row
    for *every* plugin bound to their library.

    Returns 0 when the library has no plugins bound (caller will treat
    coverage as 0/N to avoid a meaningless 100%).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    library_plugin_ids = [
        p.id
        for p in db.query(PluginModel.id)
        .join(LibraryPluginModel)
        .filter(LibraryPluginModel.library_id == library_id)
        .all()
    ]
    if not library_plugin_ids:
        return 0

    plugin_count_subq = (
        db.query(
            EntityPluginStatusModel.entity_id,
            func.count(EntityPluginStatusModel.plugin_id).label("plugin_count"),
        )
        .filter(EntityPluginStatusModel.plugin_id.in_(library_plugin_ids))
        .group_by(EntityPluginStatusModel.entity_id)
        .subquery()
    )

    return (
        db.query(EntityModel)
        .filter(EntityModel.library_id == library_id)
        .filter(EntityModel.created_at >= cutoff)
        .join(plugin_count_subq, EntityModel.id == plugin_count_subq.c.entity_id)
        .filter(plugin_count_subq.c.plugin_count == len(library_plugin_ids))
        .count()
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_processing_status_crud.py -k fully_processed -v`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add memos/crud.py tests/test_processing_status_crud.py
git commit -m "crud: count_entities_fully_processed_in_window for coverage numerator"
```

---

## Task 7: CRUD — `count_unprocessed` and `get_oldest_unprocessed_created_at`

**Files:**
- Modify: `tests/test_processing_status_crud.py` (append tests)
- Modify: `memos/crud.py` (append two helpers)

- [ ] **Step 1: Append failing tests**

```python
def test_count_unprocessed_counts_anything_missing_plugins(session):
    lib_id, _ = _seed(
        session,
        n_plugins=3,
        entity_specs=[
            (1, 3),    # fully
            (5, 2),    # missing 1
            (10, 0),   # missing all
            (60, 3),   # fully (old)
            (120, 1),  # missing 2 (old)
        ],
    )
    # 5 total, 2 fully processed → 3 unprocessed (regardless of window)
    assert crud.count_unprocessed(lib_id, db=session) == 3


def test_count_unprocessed_zero_plugins_returns_zero(session):
    lib_id, _ = _seed(session, n_plugins=0, entity_specs=[(1, 0), (5, 0)])
    assert crud.count_unprocessed(lib_id, db=session) == 0


def test_oldest_unprocessed_returns_min_created_at(session):
    lib_id, _ = _seed(
        session,
        n_plugins=2,
        entity_specs=[
            (5, 2),     # fully, ignored
            (30, 1),    # unprocessed
            (60, 0),    # unprocessed and older
            (10, 2),    # fully, ignored
        ],
    )
    oldest = crud.get_oldest_unprocessed_created_at(lib_id, db=session)
    # The oldest unprocessed was 60 minutes ago. Allow 5 second jitter.
    now = datetime.now(timezone.utc)
    age = (now - oldest).total_seconds()
    assert 60 * 60 - 5 <= age <= 60 * 60 + 5


def test_oldest_unprocessed_returns_none_when_all_processed(session):
    lib_id, _ = _seed(
        session,
        n_plugins=2,
        entity_specs=[(1, 2), (10, 2)],
    )
    assert crud.get_oldest_unprocessed_created_at(lib_id, db=session) is None


def test_oldest_unprocessed_returns_none_when_no_plugins_bound(session):
    lib_id, _ = _seed(session, n_plugins=0, entity_specs=[(1, 0), (10, 0)])
    assert crud.get_oldest_unprocessed_created_at(lib_id, db=session) is None
```

- [ ] **Step 2: Run failure**

Run: `pytest tests/test_processing_status_crud.py -k "unprocessed" -v`
Expected: FAIL — helpers missing.

- [ ] **Step 3: Implement**

Append to `memos/crud.py`:

```python
def _unprocessed_query(library_id: int, db: Session):
    """Return a query of EntityModel rows that are NOT fully processed for
    `library_id`. Returns None when the library has no plugins bound (no
    notion of 'unprocessed' applies).
    """
    library_plugin_ids = [
        p.id
        for p in db.query(PluginModel.id)
        .join(LibraryPluginModel)
        .filter(LibraryPluginModel.library_id == library_id)
        .all()
    ]
    if not library_plugin_ids:
        return None

    plugin_count_subq = (
        db.query(
            EntityPluginStatusModel.entity_id,
            func.count(EntityPluginStatusModel.plugin_id).label("plugin_count"),
        )
        .filter(EntityPluginStatusModel.plugin_id.in_(library_plugin_ids))
        .group_by(EntityPluginStatusModel.entity_id)
        .subquery()
    )

    return (
        db.query(EntityModel)
        .filter(EntityModel.library_id == library_id)
        .outerjoin(plugin_count_subq, EntityModel.id == plugin_count_subq.c.entity_id)
        .filter(
            or_(
                plugin_count_subq.c.plugin_count.is_(None),
                plugin_count_subq.c.plugin_count < len(library_plugin_ids),
            )
        )
    )


def count_unprocessed(library_id: int, db: Session) -> int:
    q = _unprocessed_query(library_id, db)
    if q is None:
        return 0
    return q.count()


def get_oldest_unprocessed_created_at(library_id: int, db: Session):
    """Return the created_at of the oldest not-fully-processed entity, or
    None if everything is processed (or no plugins are bound)."""
    q = _unprocessed_query(library_id, db)
    if q is None:
        return None
    row = q.order_by(EntityModel.created_at.asc()).first()
    return row.created_at if row else None
```

`or_` is already imported at the top of `crud.py` (used by the existing `unprocessed_only` branch in `get_entities_of_folder`). Verify before saving.

- [ ] **Step 4: Run all crud tests to verify**

Run: `pytest tests/test_processing_status_crud.py -v`
Expected: all crud tests green.

- [ ] **Step 5: Commit**

```bash
git add memos/crud.py tests/test_processing_status_crud.py
git commit -m "crud: count_unprocessed + get_oldest_unprocessed_created_at"
```

---

## Task 8: Schemas — `ProcessingStatusResponse`

**Files:**
- Modify: `memos/schemas.py` (append)

- [ ] **Step 1: Append the response schemas**

Append to `memos/schemas.py`:

```python
class ProcessingCoverageWindow(BaseModel):
    total: int
    fully_processed: int
    pct: float


class ProcessingBacklog(BaseModel):
    total_unprocessed: int
    oldest_age_seconds: int | None


class ProcessingWatchState(BaseModel):
    is_alive: bool
    is_on_battery: bool
    is_within_idle_window: bool
    idle_window: Tuple[str, str]


class ProcessingStatusResponse(BaseModel):
    library_id: int
    computed_at: datetime
    window_hours: int
    coverage_window: ProcessingCoverageWindow
    backlog: ProcessingBacklog
    watch: ProcessingWatchState
```

`Tuple` from `typing` is already imported at the top of `schemas.py`; if not, add `from typing import Tuple`.

- [ ] **Step 2: Verify schemas import cleanly**

Run: `python -c "from memos.schemas import ProcessingStatusResponse; print(ProcessingStatusResponse.model_json_schema()['required'])"`
Expected: prints the required-field list.

- [ ] **Step 3: Commit**

```bash
git add memos/schemas.py
git commit -m "schemas: ProcessingStatusResponse + window/backlog/watch sub-models"
```

---

## Task 9: Route handler — write failing integration tests

**Files:**
- Test: `tests/test_processing_status_route.py` (create)

- [ ] **Step 1: Create the test file**

```python
"""Integration tests for GET /api/libraries/{id}/processing-status."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from memos.models import (
    Base,
    EntityModel,
    EntityPluginStatusModel,
    FolderModel,
    LibraryModel,
    LibraryPluginModel,
    PluginModel,
)
from memos.schemas import LibraryKind
from memos.server import api_router, app, get_db


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def client(engine):
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    api_router.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        api_router.dependency_overrides.pop(get_db, None)


def _seed_record_lib(engine, *, n_plugins=2, entity_specs=()):
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        lib = LibraryModel(name="shots", kind=LibraryKind.RECORD)
        db.add(lib)
        db.flush()
        folder = FolderModel(
            library_id=lib.id,
            path="/tmp",
            last_modified_at=datetime.now(timezone.utc),
        )
        db.add(folder)
        db.flush()
        plugins = []
        for i in range(n_plugins):
            p = PluginModel(name=f"plugin-{i}", webhook_url=f"/p{i}")
            db.add(p)
            db.flush()
            db.add(LibraryPluginModel(library_id=lib.id, plugin_id=p.id))
            plugins.append(p)
        for created_minutes_ago, plugins_done in entity_specs:
            created_at = datetime.now(timezone.utc) - timedelta(minutes=created_minutes_ago)
            ent = EntityModel(
                filepath=f"/tmp/e-{created_minutes_ago}-{plugins_done}.png",
                filename=f"e-{created_minutes_ago}-{plugins_done}.png",
                size=1,
                file_created_at=created_at,
                file_last_modified_at=created_at,
                file_type="image/png",
                file_type_group="image",
                library_id=lib.id,
                folder_id=folder.id,
                created_at=created_at,
                updated_at=created_at,
                last_scan_at=created_at,
            )
            db.add(ent)
            db.flush()
            for p in plugins[:plugins_done]:
                db.add(EntityPluginStatusModel(entity_id=ent.id, plugin_id=p.id))
        db.commit()
        return lib.id


def _seed_static_lib(engine):
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        lib = LibraryModel(name="imports", kind=LibraryKind.STATIC)
        db.add(lib)
        db.commit()
        return lib.id


def test_returns_200_for_record_library(client, engine, monkeypatch):
    # Pin the watch predicates to a known-good "running fine" state.
    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)

    lib_id = _seed_record_lib(
        engine,
        n_plugins=2,
        entity_specs=[(5, 2), (10, 1), (20, 0), (90, 2)],
    )

    res = client.get(f"/api/libraries/{lib_id}/processing-status")
    assert res.status_code == 200
    body = res.json()

    assert body["library_id"] == lib_id
    assert body["window_hours"] == 24
    cov = body["coverage_window"]
    # All 4 are in the 24h window. 1 fully processed, 2 unprocessed, 1 fully processed (90 min ago is still in 24h).
    assert cov["total"] == 4
    assert cov["fully_processed"] == 2
    assert abs(cov["pct"] - 0.5) < 1e-6

    bk = body["backlog"]
    assert bk["total_unprocessed"] == 2
    # Oldest is the 20-min-ago one (the 10-min and 20-min ones are unprocessed; 90-min is fully).
    assert 20 * 60 - 5 <= bk["oldest_age_seconds"] <= 20 * 60 + 5

    w = body["watch"]
    assert w["is_alive"] is True
    assert w["is_on_battery"] is False
    assert w["is_within_idle_window"] is True
    assert isinstance(w["idle_window"], list) and len(w["idle_window"]) == 2


def test_returns_404_for_unknown_library(client):
    res = client.get("/api/libraries/9999/processing-status")
    assert res.status_code == 404


def test_returns_400_for_static_library(client, engine):
    lib_id = _seed_static_lib(engine)
    res = client.get(f"/api/libraries/{lib_id}/processing-status")
    assert res.status_code == 400


def test_clamps_window_hours(client, engine, monkeypatch):
    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)
    lib_id = _seed_record_lib(engine, n_plugins=1, entity_specs=[])
    # FastAPI Query(ge=1, le=168) should produce 422 on out-of-range values.
    assert client.get(f"/api/libraries/{lib_id}/processing-status?window_hours=0").status_code == 422
    assert client.get(f"/api/libraries/{lib_id}/processing-status?window_hours=169").status_code == 422
    assert client.get(f"/api/libraries/{lib_id}/processing-status?window_hours=24").status_code == 200


def test_empty_window_returns_pct_one_and_null_oldest(client, engine, monkeypatch):
    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)
    lib_id = _seed_record_lib(engine, n_plugins=2, entity_specs=[])
    body = client.get(f"/api/libraries/{lib_id}/processing-status").json()
    assert body["coverage_window"]["total"] == 0
    assert body["coverage_window"]["fully_processed"] == 0
    assert body["coverage_window"]["pct"] == 1.0
    assert body["backlog"]["total_unprocessed"] == 0
    assert body["backlog"]["oldest_age_seconds"] is None


def test_cache_skips_db_within_ttl(client, engine, monkeypatch):
    """Two calls within the TTL should produce a single set of DB hits."""
    from memos import server

    monkeypatch.setattr("memos.utils.watch_state.is_alive", lambda: True)
    monkeypatch.setattr("memos.utils.watch_state.is_on_battery", lambda: False)
    monkeypatch.setattr("memos.utils.watch_state.is_within_idle_window", lambda *a, **kw: True)

    # Force a long TTL so the second call definitely hits cache.
    monkeypatch.setattr(server, "_PROCESSING_STATUS_TTL", 60.0)
    # Clear any prior cache state.
    server._processing_status_cache.clear()

    lib_id = _seed_record_lib(engine, n_plugins=1, entity_specs=[(5, 0)])

    calls = {"n": 0}
    real_count = server.crud.count_entities_in_window

    def counting_count(*args, **kwargs):
        calls["n"] += 1
        return real_count(*args, **kwargs)

    monkeypatch.setattr(server.crud, "count_entities_in_window", counting_count)

    client.get(f"/api/libraries/{lib_id}/processing-status").raise_for_status()
    client.get(f"/api/libraries/{lib_id}/processing-status").raise_for_status()
    assert calls["n"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_processing_status_route.py -v`
Expected: FAIL — route returns 404 for every URL (the path isn't registered yet).

---

## Task 10: Route handler — implement

**Files:**
- Modify: `memos/server.py`

- [ ] **Step 1: Add the cache state next to `_collection_size_cache`**

Find the `_collection_size_cache` declaration (`memos/server.py:914`) and add right below:

```python
# Processing-status cache: same shape and TTL story as the collection-size
# one (cheap to recompute, harmless to be a few seconds stale, called by a
# 30s frontend poll).
_PROCESSING_STATUS_TTL = 10.0  # seconds
_processing_status_cache: dict = {}
_processing_status_lock = threading.Lock()
```

- [ ] **Step 2: Add the route handler**

Add anywhere after the schema imports and the `_collection_size_cache` block. A natural location is right after the `/libraries/{library_id}` GET handler. New code:

```python
@api_router.get(
    "/libraries/{library_id}/processing-status",
    response_model=ProcessingStatusResponse,
    tags=["library"],
)
def get_processing_status(
    library_id: int,
    window_hours: Annotated[int, Query(ge=1, le=168)] = 24,
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )
    if library.kind != LibraryKind.RECORD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="processing-status is only defined for record-kind libraries",
        )

    key = (library_id, window_hours)
    now_mono = time.monotonic()
    with _processing_status_lock:
        cached = _processing_status_cache.get(key)
        if cached and now_mono - cached[1] < _PROCESSING_STATUS_TTL:
            return cached[0]

    total = crud.count_entities_in_window(library_id, window_hours, db)
    done = crud.count_entities_fully_processed_in_window(library_id, window_hours, db)
    pct = 1.0 if total == 0 else done / total

    unprocessed_total = crud.count_unprocessed(library_id, db)
    oldest_dt = crud.get_oldest_unprocessed_created_at(library_id, db)
    if oldest_dt is None:
        oldest_age_seconds = None
    else:
        # oldest_dt may be naive (SQLite). Coerce to UTC for arithmetic.
        if oldest_dt.tzinfo is None:
            oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
        oldest_age_seconds = max(0, int((datetime.now(timezone.utc) - oldest_dt).total_seconds()))

    idle_window = (
        settings.watch.idle_process_interval[0],
        settings.watch.idle_process_interval[1],
    )
    response = ProcessingStatusResponse(
        library_id=library_id,
        computed_at=datetime.now(timezone.utc),
        window_hours=window_hours,
        coverage_window=ProcessingCoverageWindow(
            total=total, fully_processed=done, pct=pct
        ),
        backlog=ProcessingBacklog(
            total_unprocessed=unprocessed_total,
            oldest_age_seconds=oldest_age_seconds,
        ),
        watch=ProcessingWatchState(
            is_alive=watch_state.is_alive(),
            is_on_battery=watch_state.is_on_battery(),
            is_within_idle_window=watch_state.is_within_idle_window(idle_window),
            idle_window=idle_window,
        ),
    )

    with _processing_status_lock:
        _processing_status_cache[key] = (response, now_mono)
    return response
```

- [ ] **Step 3: Make sure the imports at the top of `memos/server.py` include the new names**

The file needs (some may already be present):

```python
from memos.utils import watch_state
from memos.schemas import (
    LibraryKind,
    ProcessingBacklog,
    ProcessingCoverageWindow,
    ProcessingStatusResponse,
    ProcessingWatchState,
    # ... existing imports
)
```

Confirm by running: `pytest tests/test_processing_status_route.py -v` and reading the import error if any.

- [ ] **Step 4: Run the route tests**

Run: `pytest tests/test_processing_status_route.py -v`
Expected: PASS — all 6 tests.

- [ ] **Step 5: Run the full backend test suite to confirm no regressions**

Run: `pytest tests/ -v --no-header 2>&1 | tail -30`
Expected: previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add memos/server.py tests/test_processing_status_route.py
git commit -m "server: GET /api/libraries/{id}/processing-status (10s TTL cached)"
```

---

## Task 11: Frontend — strip mock-only exports from `processing-status.ts`

**Files:**
- Modify: `web/src/lib/processing-status.ts`

- [ ] **Step 1: Remove the mock-only exports**

Open `web/src/lib/processing-status.ts`. Delete the following exported names (and their bodies):

- `MOCK_PAYLOADS`
- `MOCK_ORDER`
- `MOCK_LABELS`

Keep everything else (the `ProcessingStatus` interface, `PillColor`, `HeadlineKey`, `PillState`, `pillState`, `worst`, `HEADLINES`, `headlineReason`, `humanizeAge`, `humanizeComputedAt`).

- [ ] **Step 2: Run the type check**

Run: `pnpm --prefix web exec tsc --noEmit`
Expected: build will fail because `routes/index.tsx` still imports the deleted `MOCK_*`. That's fine — Task 13 fixes the import. Note the error and continue.

- [ ] **Step 3: No commit yet** — the codebase will not build until Tasks 12 + 13 land. Tasks 11–13 commit together at the end of Task 13.

---

## Task 12: Frontend — `useProcessingStatus` hook

**Files:**
- Create: `web/src/lib/api/processing-status.ts`

- [ ] **Step 1: Create the hook**

```typescript
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { ProcessingStatus } from '$/lib/processing-status';

export function useProcessingStatus(libraryId: number | undefined) {
  return useQuery({
    queryKey: ['processing-status', libraryId],
    queryFn: ({ signal }) =>
      apiFetch<ProcessingStatus>(
        `/libraries/${libraryId}/processing-status?window_hours=24`,
        { signal },
      ),
    enabled: libraryId !== undefined,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 25_000,
  });
}
```

- [ ] **Step 2: Verify the file type-checks in isolation**

Run: `pnpm --prefix web exec tsc --noEmit`
Expected: still failing because `index.tsx` references `MOCK_*`. The new hook file itself should not introduce errors — confirm the only errors are about `MOCK_PAYLOADS`/`MOCK_ORDER`/`MOCK_LABELS`.

- [ ] **Step 3: No commit yet** — see Task 11 Step 3.

---

## Task 13: Frontend — self-contained `ProcessingStatusPill` + wire into `index.tsx`

**Files:**
- Modify: `web/src/components/common/ProcessingStatusPill.tsx`
- Modify: `web/src/routes/index.tsx`

- [ ] **Step 1: Rewrite the pill to be self-contained**

Replace the entire contents of `web/src/components/common/ProcessingStatusPill.tsx` with:

```tsx
import { useMemo } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '$/components/ui/popover';
import { useLibraries } from '$/lib/api/libraries';
import { useProcessingStatus } from '$/lib/api/processing-status';
import {
  headlineReason,
  humanizeAge,
  humanizeComputedAt,
  pillState,
  type PillColor,
  type ProcessingStatus,
} from '$/lib/processing-status';
import { cn } from '$/lib/utils';

const DOT_CLASS: Record<PillColor, string> = {
  green: 'bg-emerald-500',
  yellow: 'bg-amber-500',
  red: 'bg-red-500',
  gray: 'bg-zinc-400',
};

export function ProcessingStatusPill() {
  const { data: libraries } = useLibraries();
  const recordLibraryId = useMemo(
    () => libraries?.find((l) => l.kind === 'record')?.id,
    [libraries],
  );
  const { data: status } = useProcessingStatus(recordLibraryId);

  if (!status) return null;
  return <PillButton status={status} />;
}

function PillButton({ status }: { status: ProcessingStatus }) {
  const state = pillState(status);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Processing status: ${state.headline}`}
          className={cn(
            'inline-flex h-8 items-center gap-1.5 rounded-full border border-border/70 bg-background px-2.5',
            'text-xs font-medium text-muted-foreground hover:text-foreground',
            'transition-colors hover:border-border focus-visible:outline-none focus-visible:ring-2',
            'focus-visible:ring-ring focus-visible:ring-offset-2',
          )}
        >
          <span className={cn('h-2 w-2 rounded-full', DOT_CLASS[state.color])} aria-hidden />
          <span className="tabular-nums">{state.pctText}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <PanelBody status={status} />
      </PopoverContent>
    </Popover>
  );
}

function PanelBody({ status }: { status: ProcessingStatus }) {
  const state = pillState(status);
  const reason = headlineReason(status, state.headlineKey);
  const { coverage_window: cov, backlog, watch } = status;

  return (
    <div className="text-sm">
      <div className="flex items-baseline justify-between px-4 pt-3.5 pb-2">
        <div>
          <div className="flex items-center gap-2">
            <span className={cn('h-2.5 w-2.5 rounded-full', DOT_CLASS[state.color])} aria-hidden />
            <span className="font-medium text-foreground">{state.headline}</span>
          </div>
          {reason && (
            <div className="ml-[18px] mt-0.5 text-[11px] text-muted-foreground">{reason}</div>
          )}
        </div>
        <span className="text-[11px] text-muted-foreground">
          {humanizeComputedAt(status.computed_at)}
        </span>
      </div>

      <Divider />

      <div className="px-4 py-3">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          过去 {status.window_hours} 小时
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="text-2xl font-semibold tabular-nums text-foreground">
            {(cov.pct * 100).toFixed(1)}%
          </span>
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">
          {cov.fully_processed.toLocaleString()} / {cov.total.toLocaleString()} 已全部完成插件
        </div>
      </div>

      <Divider />

      <div className="px-4 py-3">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">待处理</div>
        <div className="mt-1 text-foreground">
          <span className="font-semibold tabular-nums">
            {backlog.total_unprocessed.toLocaleString()}
          </span>{' '}
          <span className="text-muted-foreground">条</span>
          {backlog.oldest_age_seconds !== null && (
            <>
              <span className="mx-1.5 text-muted-foreground">·</span>
              <span className="text-muted-foreground">
                最老 {humanizeAge(backlog.oldest_age_seconds)}
              </span>
            </>
          )}
        </div>
      </div>

      <Divider />

      <div className="px-4 py-2.5 text-[11px] text-muted-foreground">
        <WatchFactLine watch={watch} />
      </div>
    </div>
  );
}

function WatchFactLine({ watch }: { watch: ProcessingStatus['watch'] }) {
  const parts: string[] = [];
  parts.push(watch.is_alive ? 'Watch 运行中' : 'Watch 未启动');
  parts.push(watch.is_on_battery ? '电池供电' : '已接电源');
  parts.push(`时段 ${watch.idle_window[0]}–${watch.idle_window[1]}`);
  return <span>{parts.join(' · ')}</span>;
}

function Divider() {
  return <div className="h-px bg-border/70" />;
}
```

- [ ] **Step 2: Strip the dev picker from `index.tsx`**

In `web/src/routes/index.tsx`:

1. Remove the import `import { MOCK_LABELS, MOCK_ORDER, MOCK_PAYLOADS } from '$/lib/processing-status';`.
2. Remove the line `const [mockStatusKey, setMockStatusKey] = useState<string>('processing');` inside `HomePage`.
3. In the `right={...}` slot, replace the `<select>` + `<ProcessingStatusPill status={MOCK_PAYLOADS[mockStatusKey]} />` block with just:
   ```tsx
   <ProcessingStatusPill />
   ```

The final `right` slot should be:

```tsx
right={
  <div className="flex items-center gap-1">
    <ProcessingStatusPill />
    <LanguageSwitcher />
    <ThemeToggle />
    <Link to="/config">
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-muted-foreground hover:text-foreground"
        title={t('config.title')}
      >
        <Settings size={18} />
      </Button>
    </Link>
  </div>
}
```

- [ ] **Step 3: Type-check**

Run: `pnpm --prefix web exec tsc --noEmit`
Expected: clean (no errors).

- [ ] **Step 4: Build the bundle as a final guard**

Run: `pnpm --prefix web run build 2>&1 | tail -20`
Expected: build succeeds. (`build` runs `tsc --noEmit && vite build`.)

- [ ] **Step 5: Manual browser check**

Start the dev server: `pnpm --prefix web run dev` (run in background or a separate terminal).
Open `http://localhost:5173/`. The pill should appear in the header. Click it; the panel should render with live (or empty if no record library) data. The dashed-amber `<select>` should be gone.

- [ ] **Step 6: Commit the frontend wiring**

```bash
git add web/src/lib/processing-status.ts web/src/lib/api/processing-status.ts \
        web/src/components/common/ProcessingStatusPill.tsx web/src/routes/index.tsx
git commit -m "web: processing-status pill polls the real /processing-status endpoint"
```

---

## Task 14: Frontend — pure-function tests for `pillState` and `headlineReason`

**Files:**
- Create: `web/src/lib/processing-status.test.ts`

- [ ] **Step 1: Write the unit tests**

```typescript
import { describe, expect, test } from 'vitest';
import {
  headlineReason,
  pillState,
  type ProcessingStatus,
} from './processing-status';

function fixture(overrides: Partial<ProcessingStatus> = {}): ProcessingStatus {
  const base: ProcessingStatus = {
    library_id: 1,
    computed_at: new Date().toISOString(),
    window_hours: 24,
    coverage_window: { total: 100, fully_processed: 100, pct: 1.0 },
    backlog: { total_unprocessed: 0, oldest_age_seconds: null },
    watch: {
      is_alive: true,
      is_on_battery: false,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  };
  return {
    ...base,
    ...overrides,
    coverage_window: { ...base.coverage_window, ...(overrides.coverage_window ?? {}) },
    backlog: { ...base.backlog, ...(overrides.backlog ?? {}) },
    watch: { ...base.watch, ...(overrides.watch ?? {}) },
  };
}

describe('pillState', () => {
  test('green when 100% covered and no backlog', () => {
    const s = pillState(fixture());
    expect(s.color).toBe('green');
    expect(s.headlineKey).toBe('caught_up');
    expect(s.pctText).toBe('100%');
  });

  test('yellow at 90% coverage with fresh backlog', () => {
    const s = pillState(
      fixture({
        coverage_window: { total: 100, fully_processed: 90, pct: 0.9 },
        backlog: { total_unprocessed: 10, oldest_age_seconds: 60 },
      }),
    );
    expect(s.color).toBe('yellow');
    expect(s.headlineKey).toBe('processing');
  });

  test('red when coverage below 80%', () => {
    const s = pillState(
      fixture({
        coverage_window: { total: 100, fully_processed: 70, pct: 0.7 },
        backlog: { total_unprocessed: 30, oldest_age_seconds: 10 * 60 },
      }),
    );
    expect(s.color).toBe('red');
    expect(s.headlineKey).toBe('processing');
  });

  test('red and backlog headline when oldest > 1h', () => {
    const s = pillState(
      fixture({
        coverage_window: { total: 100, fully_processed: 90, pct: 0.9 },
        backlog: { total_unprocessed: 10, oldest_age_seconds: 2 * 60 * 60 },
      }),
    );
    expect(s.color).toBe('red');
    expect(s.headlineKey).toBe('backlog');
  });

  test('gray when watch dead', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: false, is_on_battery: false, is_within_idle_window: true, idle_window: ['00:00', '23:59'] },
        backlog: { total_unprocessed: 100, oldest_age_seconds: 60 * 60 },
      }),
    );
    expect(s.color).toBe('gray');
    expect(s.headlineKey).toBe('watch_dead');
  });

  test('gray when on battery and backlog older than 5min', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: true, is_on_battery: true, is_within_idle_window: true, idle_window: ['00:00', '23:59'] },
        backlog: { total_unprocessed: 10, oldest_age_seconds: 10 * 60 },
        coverage_window: { total: 100, fully_processed: 90, pct: 0.9 },
      }),
    );
    expect(s.color).toBe('gray');
    expect(s.headlineKey).toBe('paused_battery');
  });

  test('not gray when on battery but oldest under 5min', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: true, is_on_battery: true, is_within_idle_window: true, idle_window: ['00:00', '23:59'] },
        backlog: { total_unprocessed: 1, oldest_age_seconds: 30 },
        coverage_window: { total: 100, fully_processed: 99, pct: 0.99 },
      }),
    );
    expect(s.color).not.toBe('gray');
    expect(s.headlineKey).toBe('paused_battery');
  });

  test('paused_window headline when outside idle window', () => {
    const s = pillState(
      fixture({
        watch: { is_alive: true, is_on_battery: false, is_within_idle_window: false, idle_window: ['00:00', '07:00'] },
        backlog: { total_unprocessed: 50, oldest_age_seconds: 30 * 60 },
        coverage_window: { total: 100, fully_processed: 95, pct: 0.95 },
      }),
    );
    expect(s.headlineKey).toBe('paused_window');
    expect(s.color).toBe('gray');
  });

  test('empty window (total=0) treated as caught up', () => {
    const s = pillState(
      fixture({ coverage_window: { total: 0, fully_processed: 0, pct: 1.0 } }),
    );
    expect(s.headlineKey).toBe('caught_up');
    expect(s.color).toBe('green');
  });
});

describe('headlineReason', () => {
  test('returns null for non-paused keys', () => {
    expect(headlineReason(fixture(), 'caught_up')).toBeNull();
    expect(headlineReason(fixture(), 'processing')).toBeNull();
    expect(headlineReason(fixture(), 'backlog')).toBeNull();
    expect(headlineReason(fixture(), 'watch_dead')).toBeNull();
  });

  test('returns battery copy', () => {
    expect(headlineReason(fixture(), 'paused_battery')).toBe('电池供电中');
  });

  test('returns window copy with the configured range', () => {
    const s = fixture({
      watch: {
        is_alive: true,
        is_on_battery: false,
        is_within_idle_window: false,
        idle_window: ['22:00', '06:00'],
      },
    });
    expect(headlineReason(s, 'paused_window')).toBe('处理时段外（22:00–06:00）');
  });
});
```

- [ ] **Step 2: Run the test file**

Run: `pnpm --prefix web run test -- processing-status.test.ts`
Expected: all 12 tests pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/processing-status.test.ts
git commit -m "test(web): pillState + headlineReason branches"
```

---

## Task 15: Frontend — render tests for the pill component

**Files:**
- Create: `web/src/components/common/ProcessingStatusPill.test.tsx`

- [ ] **Step 1: Check if React Testing Library is already set up**

Run: `grep -E "@testing-library/react|@testing-library/dom" web/package.json`
- If present, proceed to Step 2.
- If not present: install with `pnpm --prefix web add -D @testing-library/react @testing-library/dom @testing-library/jest-dom jsdom`, and add `test: { environment: 'jsdom' }` to `web/vite.config.ts` if it isn't already configured.

Run: `cat web/vite.config.ts` and add the test config if needed.

- [ ] **Step 2: Write the render tests**

The component normally fetches libraries + status. For tests, we render the inner `PillButton` directly with a constructed status. Refactor the component file in this task to export `PillButton`:

In `web/src/components/common/ProcessingStatusPill.tsx`, change:

```typescript
function PillButton({ status }: { status: ProcessingStatus }) {
```

to:

```typescript
export function PillButton({ status }: { status: ProcessingStatus }) {
```

Then write:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, test } from 'vitest';

import { PillButton } from './ProcessingStatusPill';
import type { ProcessingStatus } from '$/lib/processing-status';

function fixture(overrides: Partial<ProcessingStatus> = {}): ProcessingStatus {
  const base: ProcessingStatus = {
    library_id: 1,
    computed_at: new Date().toISOString(),
    window_hours: 24,
    coverage_window: { total: 100, fully_processed: 82, pct: 0.82 },
    backlog: { total_unprocessed: 18, oldest_age_seconds: 600 },
    watch: {
      is_alive: true,
      is_on_battery: false,
      is_within_idle_window: true,
      idle_window: ['00:00', '23:59'],
    },
  };
  return {
    ...base,
    ...overrides,
    coverage_window: { ...base.coverage_window, ...(overrides.coverage_window ?? {}) },
    backlog: { ...base.backlog, ...(overrides.backlog ?? {}) },
    watch: { ...base.watch, ...(overrides.watch ?? {}) },
  };
}

describe('PillButton', () => {
  test('renders percentage text', () => {
    render(<PillButton status={fixture()} />);
    expect(screen.getByText('82%')).toBeTruthy();
  });

  test('aria-label reflects headline', () => {
    render(
      <PillButton
        status={fixture({
          watch: {
            is_alive: false,
            is_on_battery: false,
            is_within_idle_window: true,
            idle_window: ['00:00', '23:59'],
          },
        })}
      />,
    );
    const btn = screen.getByRole('button');
    expect(btn.getAttribute('aria-label')).toContain('Watch 服务未启动');
  });
});
```

- [ ] **Step 3: Run**

Run: `pnpm --prefix web run test -- ProcessingStatusPill.test.tsx`
Expected: 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/common/ProcessingStatusPill.tsx web/src/components/common/ProcessingStatusPill.test.tsx
git commit -m "test(web): ProcessingStatusPill renders pct text + aria-label"
```

---

## Task 16 (optional, can ship after): i18n

**Files:**
- Modify: `web/src/locales/en.json` and `web/src/locales/zh.json`
- Modify: `web/src/lib/processing-status.ts` (headline strings)
- Modify: `web/src/components/common/ProcessingStatusPill.tsx` (panel labels)

- [ ] **Step 1: Add the `status` namespace**

To `web/src/locales/zh.json` (top-level keys):

```json
{
  "status": {
    "headline": {
      "watch_dead": "Watch 服务未启动",
      "paused": "已暂停",
      "backlog": "处理积压",
      "caught_up": "已跟上",
      "processing": "处理中"
    },
    "reason": {
      "battery": "电池供电中",
      "window": "处理时段外（{{start}}–{{end}}）"
    },
    "panel": {
      "windowTitle": "过去 {{hours}} 小时",
      "coverageSubtitle": "{{done}} / {{total}} 已全部完成插件",
      "backlogTitle": "待处理",
      "backlogCountSuffix": "条",
      "oldestPrefix": "最老 ",
      "watchAlive": "Watch 运行中",
      "watchDead": "Watch 未启动",
      "battery": "电池供电",
      "powered": "已接电源",
      "windowSuffix": "时段 {{start}}–{{end}}"
    }
  }
}
```

And the parallel English keys in `web/src/locales/en.json` (translations left to the integrator; suggested values: `"watch_dead": "Watch service not running"`, `"paused": "Paused"`, `"backlog": "Indexing backlog"`, `"caught_up": "Caught up"`, `"processing": "Processing"`, etc.).

- [ ] **Step 2: Replace hardcoded strings in `processing-status.ts` and `ProcessingStatusPill.tsx` with `t(...)` lookups**

This is mechanical:

- `pillState`'s `HEADLINES` table: turn the dict from `() => string` to returning keys like `'status.headline.watch_dead'`, and let the component call `t(key)`.
- `headlineReason`: change to return `{ key: string, params?: Record<string, string> }` shape (or `null`), and let the component call `t(key, params)`.
- Panel labels in `ProcessingStatusPill.tsx`: wrap every visible string in `t('status.panel.*', {...})`.

- [ ] **Step 3: Re-run all tests to ensure none of the i18n changes broke them**

The pure-function tests in `processing-status.test.ts` no longer assert string equality; update them to assert headline keys instead of translated text.

Run: `pnpm --prefix web run test`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add web/src/locales/en.json web/src/locales/zh.json \
        web/src/lib/processing-status.ts \
        web/src/components/common/ProcessingStatusPill.tsx \
        web/src/lib/processing-status.test.ts
git commit -m "i18n(status): move pill + panel strings under status namespace"
```

---

## Self-review

Spec coverage:

- §1 motivation → no task (motivation only).
- §2 goals: pill + panel + states + reuse "fully processed" → Tasks 5–13.
- §2 non-goals → respected (no per-plugin breakdown, no actions, no SSE).
- §3 scope/definitions → Tasks 11–13 (frontend resolves first `kind=record` library; backend 400 for static).
- §4 UX color rule, headline priority, panel layout → Tasks 11–15 use the existing pure-function tests + render tests; panel layout copied verbatim from the mock that the user already approved.
- §5 architecture and PID-based watch state → Tasks 1–3.
- §6 API contract (response shape, 404/400, window clamp) → Tasks 8–10.
- §7 backend implementation notes (CRUD helpers, cache pattern, route module location, tests) → Tasks 4–10.
- §8 frontend implementation notes (hook file location, react-query config, files) → Tasks 11–13.
- §9 mock cleanup → Tasks 11–13.
- §10 open questions: v1 has none; deferred items are out of scope.

Placeholder scan: no "TBD" / "fill in later" / "handle edge cases" remain. Every code block is concrete.

Type consistency: `ProcessingStatus` TypeScript interface and `ProcessingStatusResponse` Pydantic shape both use `coverage_window`, `fully_processed`, `pct`, `backlog.total_unprocessed`, `backlog.oldest_age_seconds`, `watch.is_alive`, `watch.is_on_battery`, `watch.is_within_idle_window`, `watch.idle_window`. CRUD helper names match: `count_entities_in_window`, `count_entities_fully_processed_in_window`, `count_unprocessed`, `get_oldest_unprocessed_created_at`. Watch utility module path `memos/utils/watch_state.py` is consistent across tasks.
