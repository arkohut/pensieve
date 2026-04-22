# Pensieve Activity Model Design

**Status**: Design (no implementation in this document)
**Author**: collaborative (arkohut + Claude)
**Date**: 2026-04-22
**POC artifacts**: `docs/superpowers/experiments/vlm_bench/`, `docs/superpowers/experiments/diagnostic_v4.py`

---

## 0. How this document is scoped

This is an **umbrella design** covering the full shape of the
activity-model feature. It deliberately does not specify file-level
implementation detail, DDL, function signatures, or library choices — those
belong to plan documents.

Expected breakdown into plans (subsequent `docs/superpowers/plans/*.md`
documents) roughly:

- **Plan 1 — Signal layer**: Layer 1 structured extractor plugin interface,
  `structured_vlm_v1` prompt committed as an asset, TZ unification across
  worklog/metadata, 30-day backfill job. Produces: reliable structured data
  per screenshot. Nothing user-visible.
- **Plan 2 — Aggregation layer**: Layer 2 AttentionTick timeline, TaskSession
  identity grouping, AttentionMoment bucket grouping. Decision on whether to
  materialize or compute-at-query. Produces: usable query primitives.
- **Plan 3 — Retrieval API + Day view**: the homepage three-zone layout
  (§8.1) wired to real data.
- **Plan 4 — Search and Task Detail views**.
- **Later plans**: contact graph, multi-image VLM, Layer 3 LLM synthesis on
  demand.

The spec below is the shared source of truth those plans refer back to.

---

## 1. Background and motivation

Pensieve today is a local screen-recording archive: the recorder takes a
screenshot every ~4 seconds (deduped by perceptual hash), OCR and VLM prose run
as plugins, and the web UI shows a reverse-chronological thumbnail grid plus
full-text / vector search.

The archive works as storage. It does not serve the retrieval experience the
user actually wants, because the product's atomic unit is "one screenshot" while
the user's mental model of their own day is "activities, tasks, and projects I
was working on". Two concrete failure modes:

- **Visual near-duplicates swamp the grid**. Homepage for an active day shows
  dozens of near-identical iTerm2 or Chrome thumbnails that are visually similar
  but semantically different (same terminal, different content). Search for
  "claude design" returns 14 near-identical Chrome frames instead of "the
  moment I read that page".
- **An existing `journal/` module (not committed) tried to fix this with VLM+LLM
  activity recognition. It produced 97 activities/day with overlapping time
  ranges, empty structured fields (`tags=[]`, `urls=[]`, `work_path=null`), and
  30-second "activities" generated from tab-switches. The design put the LLM at
  the center of extraction, which failed at structure but succeeded at prose.**

### What the user's day actually looks like (POC evidence)

Diagnostic run against 2026-04-17 (local) revealed a work pattern that no
existing activity-tracking tool models well:

- **25 distinct Claude Code / OpenCode tasks in one day**, each with 10–30
  check-ins
- **Peak 18 tasks alive simultaneously** at 15:00 local
- **Foreground ratio 0–3%** per task — the user glances at each for 30 s–2 min,
  then rotates to the next; most task time is the agent running in background
- **Workspace is a clean super-hierarchy**: 12 tasks in `openbayes-api-server`,
  5 in `rancher-gitops`, 3 in `video-understanding`, 1 in `memos`

This is an **AI-agent orchestrator work pattern**, not a "single focus, serial
tasks" pattern. Traditional activity models (RescueTime, Rewind.ai,
ActivityWatch) assume the latter and fail on the former.

### Product positioning

The product is not a "journal generator" or "daily summary tool". It is a
**retrieval-first local archive** where retrieval is the primitive and all
other surfaces (daily recap, project progress, reading lists) are named queries
on top of the same retrieval primitive. The user confirmed: *"本质是 D (retrieval)，
A/B 都是细粒度的 D 的统计结果"*.

---

## 2. Core design principle

Three layers of derived data, each with a single clear responsibility:

```
Layer 1  ─ Per-screenshot structural extraction
             (deterministic + VLM, both writing to the same schema)
              ↓
Layer 2  ─ Timeline aggregation
             (tick-based presence, gap-aware duration, transient filtering,
              identity-driven TaskSession + moment-driven AttentionMoment)
              ↓
Layer 3  ─ On-demand LLM synthesis
             (only runs when user asks — generates summaries, recaps, briefs)
```

**Key reframe**: Layer 1 exists to build a **searchable index**, not to feed
narrative generation. Layer 3 (prose / summaries) is lazy and optional.

**Key structural insight**: TaskSession and AttentionMoment have different
lifetimes and **can overlap in time**. A TaskSession represents "something I am
working on" (persistent identity, possibly 8+ hours) while AttentionMoment
represents "where my eyes were" (short-lived, exclusive). A typical second of
user time belongs to one AttentionMoment *and* multiple live TaskSessions.

---

## 2.5 Key concepts — glossary

Four new concepts are introduced on top of the existing `Screenshot`. Every
later section uses these exact names with these exact meanings. If you skim
nothing else in this document, read this section.

### The five terms

| Name | One-line meaning | Concrete example |
|---|---|---|
| **Screenshot** | A single captured image with metadata. **Existing**, unchanged. | `screenshot-20260417-152012-of-dell_s2721ds.webp`, with `active_app=iTerm2` |
| **AttentionTick** | A **4-second interval** of user presence. The atomic unit of time for all duration and grouping logic. | 15:04:12 → 15:04:16 is one tick |
| **TaskSession** | A **long-lived identity** for "an AI-agent task I'm running", keyed by `(tool, task_title)`. Spans many hours, can run **concurrently** with other TaskSessions. | `(Claude Code, "Debug gear controller blocking issue")`, first seen 06:46, last seen 17:13, 24 check-ins totaling 12 min foreground |
| **AttentionMoment** | A **short, exclusive span of foreground attention** on a non-task unit: a URL, a chat, a shell cwd, an IDE file. | "Reading Cloudflare docs, 15:04–15:07" |
| **Workspace** | A **derived project grouping** over TaskSessions and AttentionMoments. | `openbayes-api-server` → 12 TaskSessions on 2026-04-17 |

### The critical structural insight

The central innovation over traditional activity tracking: **TaskSessions
persist in the background; AttentionMoments occupy the foreground
exclusively.** At a single AttentionTick, the user's state is:

```
  foreground (exclusive):  1 AttentionMoment  OR  a check-in into 1 TaskSession
  background (0..N):       all other TaskSessions that are currently "alive"
                           (last_seen within ~2h, not retired)
  workspace (optional):    0 or 1 derived label
```

A tick contributes time to **exactly one** foreground entity. Sessions in the
background do not accumulate `fg_seconds` from that tick — they only retain
their "alive" status.

### A concrete walk-through

Here is a 15-second slice of real Friday (2026-04-17) activity to ground the
terms:

| Tick (local) | Foreground | Consumes time for | Alive in background |
|---|---|---|---|
| 15:03:44–15:03:48 | `✳ Debug gear controller blocking issue` (iTerm2) | TaskSession `(CC, Debug gear ctrl)` — check-in #14 begins | 17 other TaskSessions stay alive |
| 15:03:48–15:03:52 | same | same check-in continues (+4 s) | same |
| 15:03:52–15:03:56 | `fake-llm-openai - HyperAI` (Chrome) | AttentionMoment `browser::Chrome::fake-llm-openai` starts | 18 TaskSessions alive (Debug-gear did not retire; it just went background) |
| 15:03:56–15:04:00 | same Chrome | same AttentionMoment continues | same |
| 15:04:00–15:04:04 | `✳ Debug gear controller ...` | check-in #15 on Debug-gear (one above) — same TaskSession, new check-in | 17 alive |

Four ticks, two TaskSession check-ins (#14 and #15 on the same session, split
by a 1-tick Chrome Moment), and one AttentionMoment. The TaskSession does not
fragment across this gap — it keeps the same identity across hours.

### Workspace and hierarchy

Workspace is a **soft super-hierarchy**, not a strict parent:

- A TaskSession has **at most one** `inferred_workspace` (picked by majority
  vote from workspace signals in nearby ticks: a fish prompt `~/projects/X`,
  an IDE tab `file — X`, VLM reading visible content)
- A TaskSession may legitimately have **no workspace** if no tick ever
  revealed one (the `iterm_codex_bare` POC case: tool title alone gives no
  project clue)
- A Workspace aggregates all TaskSessions mapped to it, **plus** direct
  AttentionMoments whose foreground was workspace-signalling (Cursor with
  `— memos`, iTerm with `fish ~/projects/memos` and no task running)

### What "check-in" is and is not

"Check-in" is **not** a persistent data entity. It is a derived view of a
TaskSession: a contiguous run of foreground ticks on that session, where
"contiguous" means no gap larger than 60 s. One TaskSession has many
check-ins; 10–30 per day is typical.

### Why two types of activity (TaskSession + AttentionMoment)?

Traditional activity trackers (Rewind, RescueTime) use a single "activity"
concept: whatever is foreground. That model breaks on the AI-agent
orchestrator pattern (§1) because a task is alive and meaningful for hours
while the user's foreground rotates to other tasks, chats, or reading.

- **TaskSession** captures "what I'm working on" even while I'm not looking
  at it (the task agent runs in the background).
- **AttentionMoment** captures "where my eyes actually are right now".

Both axes matter for retrieval:
- "When did I work on the Redis rate limiter?" → TaskSession query
- "What was I reading at 15:05?" → AttentionMoment query
- "Show me the memos project this week" → Workspace query aggregating both

---

## 3. Data model

### 3.1 Screenshot (existing, unchanged)

The existing `entities` row with `metadata_entries` kv store. Untouched by this
design. The only constraint added below: timestamps are UTC (already true) and
all new consumers treat them as UTC explicitly.

### 3.2 AttentionTick (new, derived)

A conceptual row per recorder tick (every 4 s when the user is present). This
is the foundation of all duration calculations.

- **Source**: union of DB screenshots (authoritative) + worklog `Saved`/`Skipped`
  entries (fills gaps where the image didn't change)
- **Fields**: UTC timestamp, active_app (from Saved or inherited from most
  recent Saved), active_window (same), screen_name set, `saved` bool
- **Gap handling**: if the gap between ticks exceeds a threshold
  (≈ 5 minutes), the timeline breaks — the interval between is "user away",
  not attributed

AttentionTick may live as a materialized table or as a query-time derivation;
persistence is an implementation decision, not part of this design.

### 3.3 TaskSession (new)

A persistent identity for "a specific thing the user is working on over time".

- **Identity key**: `(tool, task_title)` where tool ∈ {Claude Code, OpenCode,
  ...} and task_title is the structured extraction output
- **Lifespan**: from `first_seen` to `last_seen` across all AttentionTicks
  where this identity appears. Can span a full day; overlap with other sessions
  is expected
- **Derived**: workspace (inferred), check-ins (contiguous runs where this
  session was in foreground), total foreground seconds, check-in count,
  foreground ratio
- **State**: `alive` (last_seen within N hours) or `retired` (past that)

Example row: `{tool: "Claude Code", task: "Debug gear controller blocking
issue with bayesjob", workspace: "openbayes-gear-controller", first_seen:
06:46:39, last_seen: 17:13:44, fg_sec: 720, checkins: 24, fg_ratio: 0.03}`

### 3.4 AttentionMoment (new)

Where the user's eyes were during one short cohesive span.

- **Identity key**: varies by app (URL L2 canonical for browsers,
  `(app, contact)` for chat, etc.)
- **Lifespan**: short — typically seconds to minutes
- **Non-overlapping**: at any tick, exactly one AttentionMoment is active (the
  one that owns the tick's `active_app`/`active_window`)
- **Relationship to TaskSession**: when the user is foregrounding a Claude Code
  task, the AttentionMoment for that tick belongs to that task's session. When
  the user is browsing docs during a task's wait, the AttentionMoment is
  independent (though the TaskSession is still alive in the background)

### 3.5 Workspace (super-hierarchy)

A workspace is a stable grouping of TaskSessions (and direct shell / IDE
activity) by project/repo. Derived, not authored:

- Source signals: `fish /path/<name>` iTerm prompts, `user@host:~/path` prompts,
  Cursor / IDE tab `file — workspace` format, VLM inference from visible
  content
- A workspace aggregates all TaskSessions whose `inferred_workspace` matches it
- Enables "show me all work on memos this week" queries

Workspaces do **not** form a strict parent-child relationship with TaskSessions
— a TaskSession may legitimately have `workspace=null` if no signal is visible
in any of its ticks.

### 3.6 What is *not* in this design

- **Contact / person graph** for chat apps. POC showed contact extraction is
  unreliable (1/12 samples at best) and even the VLM sometimes writes the
  contact into `notes` instead of the `contact` field. Treat chat as a
  lower-priority surface for v1; lump per-app now, refine later when we have a
  better signal (maybe OCR of the chat header + a contact whitelist).

---

## 4. Timezone strategy

**Problem observed during POC**: the codebase stores screenshot `timestamp`
metadata as UTC (per `record.py:190`) but stores the daily `worklog` file in
local time and names screenshots by local time (per `record.py:200, 313`).
This made a 24-hour analysis window straddle two local days and silently broke
the first round of POC aggregation.

**Design decision**:

- **All persisted timestamps in new tables/metadata are UTC**. Matches existing
  entity metadata behavior; no migration of existing data needed.
- **worklog format changes to UTC** for consistency (a backwards-compatible
  option: write both, prefix new lines with a marker, migrate readers). This is
  a small recorder change and keeps all future diagnostics TZ-consistent.
- **Add a `local_tz_offset` field** to each new persistence record (e.g. stored
  as "+08:00" string). This records the local offset at time of capture, so
  UI can correctly render local time even if the user later changes TZ or
  uses the data on a different host.
- **All "by day" queries** (homepage, daily recap) are explicit: they take a
  local date, convert to UTC range using the stored offset, and filter.
  Never: `WHERE ts LIKE 'YYYYMMDD%'`.

This is explicitly a design concern, not just an implementation detail, because
it bit us in the POC and will bite every future developer otherwise.

---

## 5. Layer 1 — per-screenshot structural extraction

Layer 1 produces, for every screenshot, a structured record:

```
{
  primary:     {app, what, title_or_topic, workspace}
  secondary:   [{app, what}, ...]
  contact:     string?
  url:         string?
  confidence:  {primary, contact, url}
  notes:       string?
  source_priority: [title_regex | ocr | structured_vlm | recorder_metadata]
}
```

### 5.1 Extraction sources and priority

**Structured VLM is the primary extractor for all fields.** Title regex has a
narrow, specific role: **task identity normalization** (see below). It is
*not* a general-purpose extractor.

| Source | Cost | Role |
|---|---|---|
| **Structured VLM** (`structured_vlm_v1_<model>`) | ~3 s/call on qwen3.6-35b | Primary source for `primary.app/what/title_or_topic/workspace`, `contact`, `url`, `secondary` regions, `confidence`. Covers every structural field |
| **Title regex** (`title_regex_v1`) | ~instant, deterministic | **Only** extracts `primary.tool` (Claude Code / OpenCode) and a **canonical** `primary.title_or_topic` (spinner-stripped, deterministic). Used as the stable identity source for TaskSession grouping |

Separately, two other signal sources exist but are **not** Layer 1 structural
extractors:

- **Recorder metadata** (`active_app`, `active_window`, `url`): the raw input
  that both extractors operate on. Trusted by default, but overridable by VLM
  when VLM confidence is medium+ and the two disagree — see §5.4.
- **OCR full-text** (existing, unchanged): stays as the full-text search index
  on content (chat messages, article text, code). Does **not** feed Layer 1
  structural fields directly, because POC showed VLM covers the structural
  fields (URL bar, terminal prompt, chat header) adequately without a bespoke
  OCR-crop pipeline.

**Why title regex exists at all given VLM covers everything.** POC verified
that VLM output for the same image varies across runs: spinner prefixes leak
through (`"* Migrate Svelte..."` one run, `"Migrate Svelte..."` the next).
Using VLM output directly as TaskSession identity would fragment the same
task into multiple TaskSessions across a day. The spinner-stripping,
deterministic `title_regex_v1.canonical_task_title` is the **stable identity
key** used by Layer 2 grouping. It is also a zero-cost fallback if VLM fails
for a given screenshot.

**Merge rule** (read-time, applied during Layer 2 access):
- `primary.tool` and identity-use `primary.title_or_topic`: **title regex
  wins when filled** (the whole point — deterministic identity)
- All other fields (`workspace`, `contact`, `url`, `secondary`, `what`):
  **VLM wins**. Title regex leaves these null by design.
- VLM's "visual truth" exceptions in §5.4 still apply (VLM overrides recorder
  `active_app` / `url` when confidence is medium+).

**Coverage expectation** on a typical full day (per POC §10.1 validation of
local 2026-04-17):
- 1047 screenshots (≈28%) have a CC spinner title → title regex produces a
  canonical task name + `tool=Claude Code`
- 177 screenshots (≈5%) have `OC | <topic>` → title regex produces canonical
  topic + `tool=OpenCode`
- The remaining ≈67% have no title-regex output — they rely entirely on VLM

### 5.2 The VLM prompt

Prompt is **versioned and stored alongside results**: `structured_vlm_v1`. Each
result record carries `prompt_version` and `model_name` so later changes do
not silently overwrite meaning.

The prompt asks for strict JSON with four top-level groups: `primary`,
`secondary`, top-level `contact`/`url`, `confidence`, `notes`. Full prompt
text is in `docs/superpowers/experiments/vlm_bench/prompt_v1.txt`.

### 5.3 Extractor as plugin

Layer 1 is a **plugin interface**, not a single hardcoded extractor:

- The built-in `title_regex_v1` and `structured_vlm_v1_qwen36_35b` extractors
  ship with the system, with clearly separated roles (§5.1)
- Additional VLM extractors (other models, future prompt versions) can be
  added without touching consumers
- Aggregation follows the §5.1 merge rule: VLM is primary for almost all
  fields; title regex contributes only `tool` and canonical task identity.
  When multiple VLM extractors exist (e.g., qwen + kimi), the configured
  default wins; others are stored but not consumed by default (available for
  future A/B or fallback)

This is why "test with a better model" is cheap later: write a new extractor
config, run it over some subset, consumers don't change.

### 5.4 Trust model: when VLM overrides recorder metadata

POC showed two cases where recorder metadata and visual reality disagreed:

1. `active_app=微信` but image clearly shows iTerm2 (focus switched between
   metadata capture and screenshot capture)
2. Recorder captured `url=http://localhost:3000/` but URL bar in image reads
   `beta.openbayes.com/console/openbayes/containers`

Design: **VLM output is "visual truth" and overrides recorder metadata when
confidence is medium or high**. Store both; expose "discrepancy" as a surface
for diagnostics.

---

## 6. Layer 2 — timeline aggregation

### 6.1 AttentionTick timeline construction

1. Load all screenshots in the target range (UTC-filtered by local date)
2. Load the worklog for that local date (contains Saved + Skipped entries)
3. For each unique tick timestamp, merge: known `active_app`/`active_window`
   from any Saved entry, inherit from the most recent Saved when only
   Skipped present
4. Deduplicate multi-screen entries at same timestamp (POC showed <1.5% of
   ticks and always same `active_app`, so simple dedupe is correct)

### 6.2 Gap-based duration attribution

For each tick with a successor:
- `gap ≤ 60 s`: attribute the full gap to this tick's key
- `60 s < gap ≤ 5 min`: attribute 60 s (cap; the rest is "idle or brief away")
- `gap > 5 min`: attribute the tick interval only (4 s) and mark the gap as a
  presence break (break a run even if keys match)

POC bench showed this produces plausible total time: 487 min on 4-17 (local)
from 5515 ticks, vs naive "5 s per screenshot" = 22060 s = 367 min (undercount)
or naive "fill all gaps" = 24 h (overcount).

### 6.3 Transient filter

A "transient" tick is a single-tick key-switch flanked by identical surrounding
keys where the intermediate key appears fewer than N times all day.

- Conservative parameters: exactly one tick (≤ 4 s) + same-key flanks + key
  appears total ≤ 2 ticks all day
- POC found only 17 ticks matched on 4-17, filtering ~1 minute of phantom focus

This is deliberately conservative. Brief check-ins on live Claude Code tasks
look identical to accidental clicks from signal alone; tightening the filter
risks hiding real attention.

### 6.4 TaskSession grouping

For each unique `(tool, task_title)` identity produced by Layer 1:

- Collect every tick where this identity is the primary key
- `first_seen`, `last_seen` = min/max tick timestamps
- `foreground_seconds` = sum of attributed durations (§6.2)
- `check_ins` = contiguous runs of ticks with this identity, where
  run-break threshold is 60 s gap
- `inferred_workspace` = most common non-null workspace in a ±15-tick window
  around any tick with this identity

### 6.5 AttentionMoment grouping

For non-task ticks (browse, chat, shell without task identity, IDE), apply
30-second bucket dominant-key merging:

- Bucket ticks into 30 s windows by local time
- Pick the key with the most ticks in each bucket (the "dominant" key)
- Merge consecutive buckets with identical dominant key into one
  AttentionMoment
- Moments shorter than 90 s are flagged `tiny` (retained but de-emphasized in
  UI)

This correctly handles alt-tab jitter (fast key switches within a bucket don't
fragment the moment) without requiring elaborate interrupt-absorption logic.

---

## 7. Retrieval API

The product has **one data access layer: retrieval**. All UI views in §8 are
named projections of retrieval responses. No new UI-specific aggregations,
no view-only storage.

Four primary query axes, each answering a different user intent:

| Axis | User intent | Underlying fact source |
|---|---|---|
| **by time** | "What was happening at this moment?" | AttentionTick timeline |
| **by task** | "When was I working on this task?" | TaskSession identity index |
| **by workspace** | "What did I do on this project?" | Workspace derived grouping |
| **by content** | "Find the moment about X." | OCR FTS + prose VLM vectors (existing) |

Each axis below: request shape, response shape with a concrete example, edge
cases. Endpoints are illustrative, not binding; exact routing is a plan
decision.

### 7.1 Time retrieval — `GET /api/query/time?at=<local_ts>&window=<min>`

Returns everything needed to render "what was I doing at this moment" in one
response.

```json
{
  "at": "2026-04-17T15:00:00+08:00",
  "foreground": {
    "kind": "task_checkin",                // or "moment" or "idle"
    "task_session_id": "cc_task::Debug gear controller blocking issue",
    "task_title": "Debug gear controller blocking issue with bayesjob",
    "checkin_index": 14,                   // 14th check-in of this task today
    "checkin_range": ["14:58:40", "15:01:24"],
    "screenshot_ids": [1586408, 1586411, 1586415],
    "inferred_workspace": "openbayes-gear-controller"
  },
  "alive_sessions_background": [
    {
      "task_id": "cc_task::Enable Redis rate limiter",
      "title": "Enable Redis rate limiter for GraphQL API",
      "fg_min_today": 19,
      "last_seen": "14:59:12",
      "checkins_today": 20
    }
    // … 17 more, ordered by last_seen desc
  ],
  "context_strip": {
    "before_5min": [<screenshot_ids>],
    "after_5min":  [<screenshot_ids>]
  }
}
```

Why this shape: the day-view "click on moment" interaction and the
"foreground + background" Gantt both pull from this single response. No
client-side join needed.

**Edge cases**:
- `at` falls in a presence gap (user away) → `foreground.kind = "idle"`,
  `alive_sessions_background` still returned (tasks may still be alive)
- `at` is before midnight start → `alive_sessions_background` may include
  sessions that carried over from yesterday (sessions do not reset on
  calendar days)

### 7.2 Task retrieval — `GET /api/query/task?q=<fuzzy>` and `/task/{id}`

List query (`q=Redis`):

```json
{
  "results": [
    {
      "task_session_id": "cc_task::Enable Redis rate limiter for GraphQL API",
      "tool": "Claude Code",
      "title": "Enable Redis rate limiter for GraphQL API",
      "inferred_workspace": "rancher-gitops",
      "all_time_stats": {
        "days_active": ["2026-04-15", "2026-04-17"],
        "total_fg_min": 45,
        "total_checkins": 34,
        "first_ever_seen": "2026-04-15T09:12:00+08:00",
        "last_ever_seen": "2026-04-17T17:05:11+08:00",
        "state": "alive"
      },
      "representative_screenshot_ids": [<3 typical shots>]
    }
    // …
  ]
}
```

Detail query (`/task/{id}?include=checkins,screenshots`):

```json
{
  "task": { … },
  "checkins": [
    {
      "date": "2026-04-15",
      "start": "09:12:00", "end": "09:15:30",
      "duration_sec": 210,
      "screenshot_ids": [ … ],
      "vlm_summary": null                   // lazy — populated only when user clicks Summarize (Layer 3)
    }
    // … 34
  ],
  "workspace_stats": {
    "workspace": "rancher-gitops",
    "total_tasks_in_workspace": 5
  },
  "co_occurring_sessions": [
    {"task_id": "cc_task::Debug CI pipeline timeout issues", "co_alive_seconds": 3200},
    {"task_id": "cc_task::Debug Java API server versions null assignment", "co_alive_seconds": 1450}
  ]
}
```

`co_occurring_sessions` surfaces tasks that are frequently alive simultaneously
with this one — a useful relatedness signal for the "related tasks" panel in
§8.2 and for later clustering (e.g., inferring informal sub-projects).

### 7.3 Workspace retrieval — `GET /api/query/workspace/{name}?time_range=<iso>`

```json
{
  "workspace": "memos",
  "time_range": ["2026-04-15T00:00+08:00", "2026-04-22T00:00+08:00"],
  "total_fg_min": 87,
  "task_sessions": [
    {"task_id": "cc_task::Migrate Svelte frontend to React", "title": "…", "fg_min_in_range": 52}
    // …
  ],
  "direct_attention": [
    {
      "moment_id": "ide::Cursor::library.py — memos",
      "kind": "cursor_edit",
      "fg_min_in_range": 18,
      "sample_files": ["library.py", "crud.py"],
      "sample_screenshot_ids": [ … ]
    }
  ],
  "daily_breakdown": [
    {"date": "2026-04-15", "task_fg_min": 8, "direct_fg_min": 4, "task_count": 2},
    {"date": "2026-04-17", "task_fg_min": 0, "direct_fg_min": 14, "task_count": 0}
    // …
  ]
}
```

Critical: `task_sessions + direct_attention` together are the complete
project footprint. Looking only at TaskSessions misses direct IDE / shell
work that isn't AI-agent-driven — a full workspace view must include both.

### 7.4 Content retrieval — `GET /api/search?q=<text>` (modified, preserves existing infra)

Existing FTS + vector ranking is preserved. The change: results are
**grouped by their enclosing TaskSession or AttentionMoment**, not returned
as flat screenshots.

```json
{
  "query": "claude design",
  "grouped_results": [
    {
      "container_kind": "attention_moment",
      "container_id": "browser::ChatGPT Atlas::(71) Introducing Claude Design",
      "container_title": "Introducing Claude Design by Anthropic Labs \\ Anthropic",
      "container_time_range": ["2026-04-18T21:47:00+08:00", "2026-04-18T22:15:00+08:00"],
      "matched_screenshot_count": 14,
      "representative_screenshot_id": <1 shot>,
      "expand_ids": [<all 14 screenshots>],
      "matched_fragments": ["...Claude Design, a new Anthropic Labs product..."]
    },
    {
      "container_kind": "task_checkin",
      "container_id": "cc_task::Build prototype with Claude Design",
      "container_title": "…",
      "matched_screenshot_count": 3,
      "representative_screenshot_id": <1 shot>,
      "expand_ids": [ … ]
    }
  ],
  "total_screenshots_matched": 17,
  "total_containers": 2
}
```

"14 near-identical screenshots become 1 expandable card" is the visible win;
the deeper win is that results match the user's mental model — they're
looking for *a moment*, not *a pixel-diverse image set*.

### 7.5 Shared screenshot access

Every `screenshot_id` in any response above resolves via `/api/screenshot/{id}`
to raw image + all metadata (OCR, prose VLM, structured VLM). This preserves
existing per-screenshot detail surfaces without change.

---

## 8. UI surfaces

Three views, all projections of §7 responses. No view-specific backend.

### 8.1 Day view (default homepage)

**Layout** (ASCII sketch, vertical zones top to bottom):

```
┌────────────────────────────────────────────────────────────────┐
│  ←  2026-04-17 (Friday)  →      [day | week]  [settings]       │
├────────────────────────────────────────────────────────────────┤
│ GANTT (tasks × active hours, inactive hours collapsed)         │
│         09    10    11    12    13    14    15    16    17    │
│ Debug gear ▓▓   ▓  ▓▓▓    ▓▓   ▓▓  ▓▓▓  ▓▓▓ ▓▓      ▓▓         │
│ Redis rate    ▓▓▓       ▓   ▓   ▓▓  ▓    ▓  ▓                 │
│ Svelte→React     ▓  ▓   ▓▓    ▓▓   ▓▓                          │
│ Cloudflare       ▓    ▓   ▓▓▓▓     ▓                           │
│ + 14 more ▼                                                    │
│                                                                │
│ FOREGROUND TAPE (one pixel per tick)                           │
│ ░░░▓▓▓─▓─░─▓▓▓▓─▓▓───▓▓▓▓────▓▓───▓▓▓▓─▓───▓▓────▓▓▓▓          │
│ colors: teal=task_checkin / amber=browse / grey=chat / white=idle │
├────────────────────────────────────────────────────────────────┤
│ TASKS OF THE DAY                 [sort: fg_today ▼]            │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ [thumb]  Debug gear controller blocking issue            │   │
│ │          openbayes-gear-controller                       │   │
│ │          19 min · 24 check-ins · 06:46 → 17:13           │   │
│ ├──────────────────────────────────────────────────────────┤   │
│ │ [thumb]  Enable Redis rate limiter for GraphQL API       │   │
│ │          rancher-gitops                                  │   │
│ │          19 min · 20 check-ins · 08:26 → 17:45           │   │
│ └──────────────────────────────────────────────────────────┘   │
│ + 23 more tasks ▼                                              │
├────────────────────────────────────────────────────────────────┤
│ MOMENTS (non-task attention)                                   │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ [thumb]  Cloudflare edge auth docs         15:04 (3 min) │   │
│ │          workers.cloudflare.com                          │   │
│ ├──────────────────────────────────────────────────────────┤   │
│ │ [thumb]  企业微信 服务器🔥 group            15:07 (2 min) │   │
│ │          (network packet drops alert)                    │   │
│ └──────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

**Data source**: `GET /api/query/time` for every tick or batched per-5-minute
bucket for the Gantt; `GET /api/query/workspace/*` in summary mode for the
daily task list and moments list.

**Task list sort**: `fg_today desc` by default. Other sorts (last_seen,
total_span) are future nice-to-haves but not required for v1.

**Interactions**:

| Action | Behavior |
|---|---|
| Click Gantt band (task row) | Scroll to TASKS list, highlight card. Re-click → §8.2 Task detail |
| Click Gantt at empty position (between bands) | Open in-place "moment pop-up": `GET /api/query/time` for that exact instant |
| Click TASK card | Open §8.2 Task detail |
| Click MOMENT card | Expand card to full screenshot grid for that moment |
| Gantt horizontal zoom | Four presets: day / 09-18 / 3-hour / 30-min |
| Hover foreground tape | Tooltip at tick precision: "15:04:12, reading Cloudflare docs" |

**Density handling** (from 4-17 data sample: 25 tasks, 553 tiny moments, 16h
span):
- Gantt defaults to Top 8 tasks by `fg_today`; "+N more" expands
- Moments list hides `tiny` (<90 s) by default; toggle reveals
- Gantt time axis compresses inactive hours (no activity between 01:00 and
  08:00 collapses to a single marker)

**Work-mode auto-adaptation**:
- If `len(alive_tasks_today) >= 10` → Gantt is the hero, task list prominent
  (4-17 "orchestrator" mode)
- Otherwise → foreground tape and workspace summary prominent, Gantt
  de-emphasized (3-20 "direct coder" mode)
- Switch is automatic; no user toggle in v1

### 8.2 Task detail view

```
┌───────────────────────────────────────────────────────────────┐
│  ← Back   Debug gear controller blocking issue with bayesjob  │
│  openbayes-gear-controller · Claude Code                      │
├───────────────────────────────────────────────────────────────┤
│ STATS                                                         │
│  Span today:    06:46 → 17:13  (10h 27m)                      │
│  Foreground:    19 min across 24 check-ins                    │
│  Days active:   4-15, 4-16, 4-17                              │
│  Related:       Debug CI pipeline timeout (co-alive 3200s)    │
│                 Debug Java API server versions (co-alive 1450s)│
│                                                               │
│ CHECK-INS (24)                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ #1  06:46:39 → 06:47:12   33s  [thumb][thumb][thumb]    │  │
│  │ #2  06:58:10 → 07:01:34  204s  [thumb][thumb] … (+5)    │  │
│  │ #3  07:45:00 → 07:45:48   48s  [thumb]                  │  │
│  │ ...                                                     │  │
│  │ #14 14:58:40 → 15:01:24  164s  [thumb][thumb] … (+8)    │  │
│  │ ...                                                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│ SCREENSHOTS (132)        [sort: time ▼]   [grid | timeline]   │
│ [... thumbnail grid, grouped by check-in ...]                 │
│                                                               │
│ [ Summarize this task → ]  (triggers Layer 3 LLM, lazy)       │
└───────────────────────────────────────────────────────────────┘
```

**Data source**: `GET /api/query/task/{id}?include=checkins,screenshots`.

**Interactions**:

| Action | Behavior |
|---|---|
| Click a check-in row | Expand to show all screenshots in that check-in |
| Click screenshot thumbnail | Open existing screenshot detail page |
| Click related task | Navigate to that task's detail |
| Click Summarize | Trigger Layer 3 LLM: feed representative screenshots + check-in metadata → return markdown summary, attach to task session |

A date-range control (not drawn) flips stats from "today" to
"this week / this month / all time" by re-querying with a different range.

### 8.3 Search view

```
┌────────────────────────────────────────────────────────────────┐
│ [ Search screenshots, tasks, moments...           ]  [⚙]       │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ Filter: [Time ▼] [Workspace ▼] [App ▼] [Task ▼]          │   │
│ │ Active: workspace=memos · last 7 days                    │   │
│ └──────────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────────┤
│ RESULTS: 17 screenshots in 2 containers                        │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐   │
│ │ [rep img]  Introducing Claude Design by Anthropic…       │   │
│ │            ChatGPT Atlas · 2026-04-18 21:47              │   │
│ │            14 similar screenshots in this moment (28 min)│   │
│ │            "...Claude Design, a new Anthropic Labs…"     │   │
│ │            [ Expand 14 screenshots ▼ ]                   │   │
│ ├──────────────────────────────────────────────────────────┤   │
│ │ [rep img]  Build prototype with Claude Design            │   │
│ │            TaskSession · Claude Code · 2026-04-18        │   │
│ │            3 matching screenshots                        │   │
│ │            [ View task detail → ]                        │   │
│ └──────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

**Data source**: `GET /api/search?q=<text>` (§7.4).

**Key design traits**:
1. Results always grouped by container (moment or task), never a flat
   screenshot grid
2. Filters are **facet drill-down**, not query reset — adding a workspace
   filter narrows the current result set
3. Empty states distinguish:
   - "No matches" → hint to relax filters
   - "Archive empty for this time range" → hint to check recorder status

**Saved queries** (three buttons shown above the search input):

| Button | Underlying query |
|---|---|
| **Yesterday** | `/api/query/time?at=<yesterday 00:00>&window=1440` (day view) |
| **This week on memos** | `/api/query/workspace/memos?time_range=this_week` |
| **All debugging tasks** | `/api/query/task?q=Debug` |

These are not independent features — they're the user's original A/B/E
scenarios (daily recap / project progress / auto-journal seed) realized as
named shortcuts on §7. No new backend code.

### 8.4 View transitions

```
   Day view ──click task card──→ Task detail
      │                           │
      │                           ├──click Summarize──→ Layer 3 LLM call
      │                           │                     (markdown output)
      │                           └──click related─────→ other Task detail
      │
      ├──click moment in Gantt/tape──→ Moment pop-up (§7.1 inline)
      │
      ├──search box──→ Search view ──click moment container──→ screenshot grid
      │                              │
      │                              └──click task container──→ Task detail
      │
      └──workspace breadcrumb──→ Day view scoped to that workspace
                                 (same view, filtered /api/query/workspace)
```

---

## 9. Known data integrity issues to fix

POC surfaced two bugs in the existing recorder, which this design assumes will
be fixed (or worked around via Layer 1 VLM trust). Both are tracked separately
from this spec but are prerequisites to Layer 1 trusting recorder metadata
fully.

1. **`active_app` can be stale relative to the image**. Focus changes between
   `get_active_window_info()` call and the screenshot capture, causing the
   captured `active_app` / `active_window` to not match the actual image
   content. Workaround: VLM's `primary.app` overrides when confidence is
   medium+.
2. **`url` captured by recorder can be from a different tab than the
   foreground image**. Workaround: VLM-read URL overrides recorder URL when
   the two disagree.

---

## 10. Backfill strategy

### 10.1 Delivery mechanism: builtin plugin + existing trigger pipeline

`structured_vlm_v1_<model>` ships as a **builtin plugin** (registered in
`memos/databases/initializers.py` alongside `builtin_ocr` / `builtin_vlm`).
Users opt in by adding `builtin_structured_vlm` to `default_plugins` in
`~/.memos/config.yaml` and running `memos init` (idempotent upsert + binding
to the default library).

Once enabled:

- **New screenshots** auto-process via the existing plugin pipeline
  (`trigger_webhooks` in `memos/server.py`, with idempotency via
  `crud.get_pending_plugins`).
- **Historical 30-day window** reprocesses via the same existing Pensieve
  mechanism — no new backfill CLI. Exact invocation (likely `memos lib …` or
  a short script that POSTs to the plugin webhook for entities in a date
  range) is left to the operator.

Expected cost: local GPU time only; no external API spend. Stored as
`structured_vlm_v1_<model>` metadata key per entity; the prose
`qwen3.5_35b_result` VLM field is **not** deprecated and coexists.

### 10.2 Evaluation gate

Before extending to full history, evaluate the first 30 days of output:

- Workspace fill-rate — should reach ~50%+ on real-world days (75% on the
  curated POC sample)
- Task identity consistency — same task across days produces matching keys
- No obvious Layer 2 regressions — nothing breaks the homepage day view

If clean, extend to full history. If not, iterate on the prompt → v2 → rerun
just the problem subset.

### 10.3 Prompt versioning

Stored result field name encodes both model and prompt version:
`structured_vlm_v1_qwen36_35b`. Future changes get new field names. Multiple
versions can coexist; aggregation picks the highest-priority available one.
Never mutate old values — always write a new field.

---

## 11. Out of scope for this design

Explicitly deferred:

- **Contact / person graph** (§3.6). Needs a better signal than current VLM.
- **Multi-image VLM extraction**. POC discussed pros/cons; for Layer 1, single
  image is simpler and tested. Multi-image may come later as an enhancement
  or for Layer 3 (session summarization).
- **Layer 3 LLM synthesis itself**. Only the "when and how it's triggered"
  surface is specified; the prompt and output format are a separate design.
- **Deterministic re-extraction on prompt changes**. v1 result is frozen; v2
  is additive. Strategies for selective re-run are deferred.
- **Confidence calibration**. The VLM returns self-reported confidence, which
  POC showed is unreliable (all "high" even when wrong). True confidence must
  come from cross-source agreement or multi-sample voting; that's a v2 topic.

---

## 12. POC evidence index

All referenced data and code in `docs/superpowers/experiments/`:

- `vlm_bench/` — 12-sample benchmark with prompt, `qwen3.6-35b` baseline
  results, `kimi-k2.6` comparison results, reusable runner and diff tool
- `vlm_bench/README.md` — model comparison table (qwen tied with kimi on
  workspace, kimi wins on split-pane detection 6/12 vs 2/12, qwen 22× faster
  and 60× cheaper)
- `diagnostic_v4.py` / `diagnostic_v4_20260417.json` — the tick-timeline
  diagnostic for local 2026-04-17 that grounds all §1 metrics and §6
  parameter defaults

---

## 13. Open questions

1. **Temperature=0 vs multi-sample for backfill**: POC showed same model +
   same sample produces different outputs across runs. For backfill, do we
   accept this (one-shot, move on) or do 3-sample majority vote (3× cost,
   higher structural consistency)? Default proposal: one-shot for Phase 1,
   re-evaluate after seeing 30-day output quality.
2. **Persistence of AttentionTick and TaskSession**: materialize as tables or
   compute on demand? Depends on expected query volume and data size, and
   interacts with how Phase 1 backfill is designed. Deferred to plan stage.
3. **worklog migration to UTC**: should worklog change now (simple but
   touches recorder) or at a later breaking version bump? Deferred to plan.
