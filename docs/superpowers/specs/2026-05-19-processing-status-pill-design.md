------

------

------

# Processing Status Pill Design

**Status**: Design (no implementation in this document)
**Author**: collaborative (arkohut + Claude)
**Date**: 2026-05-19
**Mock artifacts**: `web/src/components/common/ProcessingStatusPill.tsx`,
`web/src/lib/processing-status.ts`, `.claude-shots/pill-panel-*.png`

---

## 1. Background and motivation

Pensieve's homepage shows the most recent screenshots and a search box backed by
OCR and VLM-derived metadata. Capture is continuous; plugin processing runs
asynchronously and is gated by power state, battery, and the configured idle
window. In steady use there is always a tail of recently captured entities that
have not yet finished all plugins, and during pauses (battery / outside the
configured window / `watch` not running) that tail can grow into thousands of
unprocessed entities without any indication in the UI.

The product failure mode is **misattribution**:

> User searches for "the K-line chart I saw yesterday on the LG monitor", gets
> two thin hits, and concludes "this thing can't even find that — the product
> doesn't work." In reality the relevant minute is captured on disk but its OCR
> + VLM hasn't run yet because the laptop was on battery for the afternoon.

The user wrongly attributes incomplete data to a weak product. We need the UI
to **honestly surface index completeness** so the user can correctly
distinguish "the app doesn't have this" from "the app has this but hasn't
finished indexing it yet".

---

## 2. Goals and non-goals

### Goals (v1)

- A small always-visible pill in the page header that conveys "how complete is
  the recent index" at a glance.
- A click-to-expand panel that shows the underlying facts (24h coverage,
  backlog size, oldest unprocessed entity, watch service state).
- Cover the meaningful states: actively processing, caught up, deep backlog,
  paused (battery), paused (outside window), watch not running.
- Reuse the existing "fully processed" definition (all library plugins
  produced an `entity_plugin_status` row), so the pill semantics match what
  every other part of the system already calls "unprocessed".

### Non-goals (v1)

- **No prescriptive guidance.** The panel states facts ("电池供电中",
  "处理时段外") but does not tell the user what to do. v1 is a pure honesty
  signal, not a diagnostic or recovery assistant.
- **No action buttons.** No "restart watch", no "process now ignoring
  battery", no "switch processing window". Adding actions multiplies the
  backend surface and turns a passive indicator into an active control.
- **No per-plugin breakdown.** Users do not know what OCR vs VLM vs
  `structured_vlm` does; surfacing per-plugin coverage is diagnostic noise.
  Defer to v2.
- **No cross-library aggregation.** Scope is a single `kind = RECORD`
  library. Most installations have one. Multi-record-library is rare and can
  be added later.
- **No real-time push.** A 30-second poll is more than fine for a coarse
  completeness indicator. SSE / websocket pushes add infrastructure for
  marginal latency improvement.
- **No history view.** The pill shows current state, not a time series of
  past coverage.

---

## 3. Scope and definitions

### Which library?

The pill watches the first `Library` whose `kind == RECORD`. `LibraryKind` is
already a domain concept in `memos/schemas.py`:

```python
class LibraryKind(str, Enum):
    RECORD = "record"   # continuous capture stream (the home library)
    STATIC = "static"   # imports / demos / photo archives
```

If no `RECORD` library exists (rare — e.g. fresh install with only static
imports), the pill does not render. This is the honest answer: there is no
continuous-capture stream whose freshness matters.

Multiple `RECORD` libraries are technically possible but not how the system
is used in practice (`watch` is configured to feed one folder). v1 picks the
first `RECORD` library returned by `/libraries`. If multi-record-library
installations become real, this becomes a follow-up decision (see §10).

### What does "processed" mean?

An entity is **fully processed** iff every plugin bound to the entity's
library has produced a row in `entity_plugin_status` for that entity. This is
already how `crud.get_entities_of_folder(unprocessed_only=True)` works. The
pill's coverage numerator reuses this definition. There is no parallel
definition.

### What window?

- **Coverage**: rolling 24 hours of newly-created entities. This is the
  window most likely to drive a user's search experience (today, yesterday).
- **Backlog**: not windowed — `total_unprocessed` and `oldest_age_seconds`
  cover all entities not fully processed, regardless of age. Old backlog
  exists; the user should see it.

---

## 4. UX

### Pill (always visible)

The pill lives in `PageHeader`'s `right` slot as the leftmost item in the
right cluster, before `LanguageSwitcher`. Visual:

```
[ ● 87% ]
```

- Colored dot (4 colors, see below) + integer percentage of 24h coverage.
- Click toggles the panel.
- ARIA label exposes the headline state for screen readers.

### Color rule

Two dimensions drive color; the pill takes the worse of the two:

| Dimension | Green | Yellow | Red |
| --- | --- | --- | --- |
| 24h coverage `pct` | ≥ 95% | 80–95% | < 80% |
| Oldest unprocessed age | ≤ 5 min | 5 min – 1 h | > 1 h |

A **gray** override applies when the system is not currently making progress
and there is non-trivial backlog. Specifically:

```
gray  if   !watch.is_alive
       OR  (watch.is_on_battery || !watch.is_within_idle_window)
           AND oldest_age_seconds > 5min
```

The "and oldest > 5min" guard prevents a momentarily-on-battery or
just-entered-window-edge state from going gray when there is essentially no
work to do.

### Headline (panel top)

Computed by priority — first match wins:

| Priority | Condition | Headline | Reason subtitle |
| --- | --- | --- | --- |
| 1 | `!is_alive` | `Watch 服务未启动` | — |
| 2 | `is_on_battery` | `已暂停` | `电池供电中` |
| 3 | `!is_within_idle_window` | `已暂停` | `处理时段外（{start}–{end}）` |
| 4 | `oldest > 1h` | `处理积压` | — |
| 5 | `pct >= 0.95 && oldest <= 5min` | `已跟上` | — |
| 6 | else | `处理中` | — |

The reason subtitle for paused states is rendered as a small line directly
under the headline (the headline itself stays short). This avoids the verbose
`暂停（电池供电）` / `暂停（处理时段外，00:00–07:00）` titles in earlier
sketches.

### Panel content (popover, ~320px wide)

```
┌──────────────────────────────────────┐
│ ● 已暂停                    12秒前更新 │
│   电池供电中                          │
├──────────────────────────────────────┤
│ 过去 24 小时                          │
│   82.5%                              │
│   3,520 / 4,267 已全部完成插件        │
├──────────────────────────────────────┤
│ 待处理                                │
│   1,247 条 · 最老 35 分钟前           │
├──────────────────────────────────────┤
│ Watch 运行中 · 电池供电 · 时段 00:00–23:59 │
└──────────────────────────────────────┘
```

- **Headline** (with reason subtitle when applicable) + "X 秒前更新" timestamp.
- **24h block**: big percentage, then `{numerator} / {denominator} 已全部完成插件` underneath.
- **Backlog block**: total unprocessed count + oldest-age humanized.
- **Watch fact line** (footer): plain facts about the watch service state — alive/dead, power source, configured idle window. Not advice.

---

## 5. Architecture and data flow

```
┌──────────────────────────────────────────────────────────────┐
│ Browser                                                       │
│   <ProcessingStatusPill /> in PageHeader.right                │
│   ──click──> <Popover><PanelBody /></Popover>                 │
│       ▲                                                       │
│       │ useProcessingStatus(libraryId)                       │
│       │   react-query: refetchInterval=30000,                │
│       │                refetchOnWindowFocus=true             │
└───────┼───────────────────────────────────────────────────────┘
        ▼
  GET /api/libraries/{id}/processing-status?window_hours=24
        │
┌───────┼───────────────────────────────────────────────────────┐
│ Server (FastAPI)                                              │
│   - 10s TTL cache, key = (library_id, window_hours)           │
│   - crud.count_entities_in_window(...)                        │
│   - crud.count_entities_fully_processed_in_window(...)        │
│   - crud.count_unprocessed(...)                               │
│   - crud.get_oldest_unprocessed_age_seconds(...)              │
│   - utils.watch.is_alive()      ← PID file + os.kill(pid, 0)  │
│   - utils.watch.is_on_battery() ← psutil.sensors_battery()    │
│   - utils.watch.is_within_idle_window()                       │
└───────────────────────────────────────────────────────────────┘
```

### `libraryId` resolution (frontend)

The frontend already loads `/libraries` via `useLibraries()`. The pill picks
the first library where `kind === 'record'`. If none exists, the pill does not
render.

### Caching

A 10-second server-side TTL cache (matching the pattern used for
`count_entities` in the recent search-total-count work) plus a 30-second
client poll yields at most 6 DB hits per minute per active session, regardless
of how many tabs the user has open. The cache key includes `library_id` so
different libraries don't collide.

### Cross-process state (watch)

`watch` and `serve` are separate processes. Service Manager already maintains
PID files at `~/.memos/pids/{watch,serve,record}.pid` (added in commit
`e184505`). The server reads the watch PID file and signal-zero-checks the
process to determine liveness:

```python
def watch_alive() -> bool:
    pid = service_manager.read_pid_file("watch")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
```

`is_on_battery()` and `is_within_idle_window()` are pure runtime checks that
the server can do directly without IPC. No new infrastructure is introduced.

---

## 6. API contract

```
GET /api/libraries/{library_id}/processing-status
    ?window_hours=24      (optional, default 24, clamp [1, 168])

200 OK
{
  "library_id": 6,
  "computed_at": "2026-05-19T05:21:15Z",
  "window_hours": 24,
  "coverage_window": {
    "total": 4267,
    "fully_processed": 3520,
    "pct": 0.825
  },
  "backlog": {
    "total_unprocessed": 1247,
    "oldest_age_seconds": 2100
  },
  "watch": {
    "is_alive": true,
    "is_on_battery": false,
    "is_within_idle_window": true,
    "idle_window": ["00:00", "23:59"]
  }
}

404  if library_id does not exist
400  if library exists but kind != record (the pill is only meaningful for RECORD libraries)
```

Notes:

- `coverage_window.pct` is `fully_processed / total` (or `1.0` when
  `total == 0` — an empty window is "complete by vacuous truth", which is the
  honest framing).
- `backlog.oldest_age_seconds` is `null` when `total_unprocessed == 0`.
- `idle_window` echoes the configured `settings.watch.idle_process_interval`.
- `computed_at` is ISO-8601 UTC. The frontend humanizes locally.

---

## 7. Backend implementation notes

### New CRUD helpers (`memos/crud.py`)

All take `(library_id, db)` and one of them takes `window_hours`.

- `count_entities_in_window(library_id, window_hours, db) -> int`
  — `SELECT COUNT(*) FROM entities WHERE library_id = ? AND created_at >= now() - window`.
- `count_entities_fully_processed_in_window(library_id, window_hours, db) -> int`
  — Same window, restricted to entities whose `entity_plugin_status` row
  count equals the count of `library_plugins` rows for the library.
- `count_unprocessed(library_id, db) -> int`
  — Entire library, not windowed. Reuses the `unprocessed_only=True` filter
  logic already in `get_entities_of_folder`.
- `get_oldest_unprocessed_created_at(library_id, db) -> datetime | None`
  — `MIN(created_at)` of unprocessed entities; `None` if none unprocessed.

These helpers exist so the route handler can compose them. The age-in-seconds
conversion happens at the route layer (so the underlying helper stays
testable without mocking `now()`).

### Watch state utilities (`memos/utils/watch_state.py` — new module)

Extract the three predicates from `memos/cmds/library.py`:

- `is_alive() -> bool` (new, uses `service_manager.read_pid_file("watch")`)
- `is_on_battery() -> bool` (existing, currently in `cmds/library`; move to
  shared module so the server route can import it without importing watch
  command code)
- `is_within_idle_window() -> bool` (existing logic, currently inline in the
  `WatchHandler` class; extract to free function reading `settings.watch.idle_process_interval`)

### Route handler

New file `memos/routers/processing_status.py` registered into the main app.
Composes the four crud helpers + three watch utilities, applies the 10s TTL
cache, returns the response shape from §6. Returns `404` for unknown library,
`400` for non-RECORD library.

### Tests

- `tests/test_processing_status_crud.py` — in-memory SQLite fixtures with
  synthetic entities + plugins + plugin-status rows; verify each crud helper
  in isolation.
- `tests/test_processing_status_route.py` — TestClient integration: shape,
  pct rounding behavior, window clamping, 404/400 paths, cache hit (two calls
  within 10s should produce one DB round-trip).
- `tests/test_watch_state.py` — temp PID file scenarios for `is_alive`
  (file missing, file with dead pid, file with own pid).
- `is_on_battery` and `is_within_idle_window` can be mocked or tested via
  freeze/monkeypatch — keep these orthogonal.

---

## 8. Frontend implementation notes

### Files

- `web/src/lib/api/processing-status.ts` — `useProcessingStatus(libraryId)`
  react-query hook. Returns typed `ProcessingStatus`. Configured with
  `refetchInterval: 30000`, `refetchOnWindowFocus: true`,
  `staleTime: 25_000`, `enabled: !!libraryId`.
- `web/src/lib/processing-status.ts` — already exists from the mock. Pure
  functions: `pillState(s)`, `headlineReason(s, key)`, `humanizeAge(s)`,
  `humanizeComputedAt(iso)`. Mock payloads and dev picker labels live here
  for the prototype phase; they will be removed when the real hook lands.
- `web/src/components/common/ProcessingStatusPill.tsx` — already exists. Pill
  + popover panel. The current mock passes `status` as a prop; the real
  component will resolve `recordLibraryId` from `useLibraries()` and call
  `useProcessingStatus` internally, falling back to nothing (`null`) while
  loading or when no RECORD library exists.

### Tests (vitest)

- `processing-status.test.ts` — pure-function tests for `pillState` across
  the six headline keys + each color-rule edge (95%/80% pct, 5min/1h age
  cutoffs, gray-override conditions).
- `ProcessingStatusPill.test.tsx` — render with each mock payload, assert
  dot color class + percentage text + headline text + reason subtitle
  presence/absence.

### i18n

The mock currently hardcodes Chinese strings. When the design is locked, all
visible strings (headline labels, reason subtitles, footer fact-line tokens,
window-block labels, backlog-block labels) move under a `status.*` namespace
in `web/src/locales/{en,zh}.json`. This is a mechanical task and not part of
the spec scope.

---

## 9. Mock prototype in repo

A working static mock landed during brainstorming so the visual could be
validated before locking the spec:

- `web/src/lib/processing-status.ts` — types, color rule, six representative
  mock payloads (one per headline state), helpers.
- `web/src/components/common/ProcessingStatusPill.tsx` — pill + popover panel
  taking a payload as a prop.
- `web/src/routes/index.tsx` — pill mounted in the header right cluster
  alongside a small dashed-border `<select>` that lets a developer flip
  through mock states locally.

This mock is not wired to any API. It exists for visual review only. The
implementation plan starts by deleting the mock picker and replacing the
hardcoded payload with the real `useProcessingStatus` hook. The `pillState` /
`headlineReason` helpers in `web/src/lib/processing-status.ts` carry over to
production unchanged; only the `MOCK_*` exports get removed.

---

## 10. Open questions and future work

### Open for v1

None — all decisions captured above.

### Deferred to later versions

- **Per-plugin coverage breakdown.** Useful for diagnosing which layer is the
  bottleneck (OCR vs VLM vs structured_vlm) but not for the honesty-signal
  job v1 is doing. v2.
- **Click-through to unprocessed entities.** "Show me the 1,247 not-yet-
  processed entities." Requires a new filter in the search UI. v2 or later.
- **In-panel controls.** "Restart Watch", "Process now ignoring battery",
  etc. Requires new backend mutation endpoints and rethinking the
  battery/window policy as advisory rather than enforced. v2 or later, and
  likely needs its own design pass.
- **Cross-library aggregation.** If multi-RECORD-library installs become
  common, an aggregate-or-pick-active model would be needed. Not v1.
- **History / trend.** A small sparkline of coverage over the last 24 hours
  is tempting but adds another query, another chart component, and another
  rendering surface to maintain. v2.
- **True watch IPC.** Reading watch's actual current state (busy, idle-processing,
  cycle-throughput) requires watch exposing it (HTTP endpoint or a status
  file written periodically). v1's PID-file liveness check is enough to
  catch the user-actionable failure ("watch is dead") without that.
