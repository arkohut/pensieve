---
name: pensieve-search
description: Search the user's local Pensieve screenshot archive by text, app, or time range. Use when the user asks to find a screenshot ("find that thing I looked at last week", "show me when I was working on the Mastra integration", "find screenshots of the YouTube video about X"), or to locate a specific moment in time across captured activity. Returns ranked entity_ids with filepaths, timestamps, OCR snippets, and VLM-extracted structured metadata (app, topic, workspace). Can open the image locally for the user. Skip when the user wants aggregated stats, time-series analytics, or cross-day project rollups — those need separate tools.
---

# Pensieve Search Skill

Pensieve (`memos`) continuously captures screenshots and indexes them. This skill teaches you to query that index over its HTTP API.

## Where the data lives

- **Server**: `http://127.0.0.1:8839` by default (config: `server_host` / `server_port`).
  - Override with `MEMOS_SERVER_HOST` / `MEMOS_SERVER_PORT` env vars or `~/.memos/config.yaml` if the user has a non-default setup. Confirm with the user if the default doesn't respond.
- **Screenshots on disk**: `~/.memos/screenshots/YYYYMMDD/<entity>.webp`. The API returns `filepath` directly so you don't have to compute it.
- **Web UI** (same server, browser-friendly):
  - **Search page** (mirrors API filters as URL params): `http://127.0.0.1:8839/?q=...&start=...&end=...&app_names=...&library_ids=...` — you should always offer this URL in your reply so the user can click and verify results visually.
  - **Entity detail page**: `http://127.0.0.1:8839/entities/<id>` — opens one specific screenshot in context with its metadata. Offer this for any hit you cite.
  - **Config page**: `http://127.0.0.1:8839/config` — surface this if the user asks about settings.

## Pre-flight check

Before the first query in a session, verify the server is up:

```bash
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8839/api/search?q=test"
```

`200` means good. `000` or connection-refused means memos isn't running — tell the user to start it (`memos serve` or system-service).

**Always quote the URL** — the `?` and `&` are zsh glob characters and will fail with `no matches found` if unquoted. Every `curl` example below assumes a quoted URL.

## The endpoint

```
GET /api/search
```

Parameters:

| Param | Type | Notes |
|---|---|---|
| `q` | string | Full-text query (jieba-tokenized; works for Chinese + English mixed). Empty `q=""` returns recent screenshots without ranking. |
| `start`, `end` | int (UNIX seconds, UTC) | Time window on `file_created_at`. Both required together. |
| `app_names` | string | Comma-separated `active_app` values, e.g. `"Google Chrome,iTerm2"`. |
| `library_ids` | string | Comma-separated; usually leave unset to query all. |
| `limit` | int 1..200 | Default 48. Use 10–20 for casual queries, 200 only when scanning. |
| `facet` | bool | Include `facet_counts` (per-app counts), `date_range` (`earliest`/`latest`), and `date_buckets` (count per day or month, see Strategy 5). Set true on broad queries to help narrow. |
| `date` | string | Bucket filter, `YYYY-MM` or `YYYY-MM-DD`. Intersected with `start`/`end`. |

Returns `SearchResult { hits: [...] }`. Each hit:

```json
{
  "document": {
    "id": "12345",
    "filepath": "/Users/.../screenshots/20260423/00001.webp",
    "file_created_at": "2026-04-23T04:18:21+00:00",
    "tags": [],
    "metadata_entries": [
      {"key": "active_app", "value": "iTerm2", "source": "..."},
      {"key": "active_window", "value": "✳ Debug memos service background job issue", "source": "..."},
      {"key": "ocr_result", "value": "...long JSON of OCR boxes...", "source": "ocr"},
      {"key": "structured_vlm_v1_qwen3_6_35b", "value": {"primary": {"app": "Claude Code", "title_or_topic": "...", "what": "...", "workspace": "memos"}}, "source": "structured_vlm"},
      ...
    ]
  }
}
```

The `metadata_entries` is the goldmine — the VLM-extracted structured fields (`primary.app`, `primary.title_or_topic`, `primary.what`, `primary.workspace`) live inside the `structured_vlm_v1_*` entry's `value`. **The `value` is a parsed JSON object, not a string** — access fields directly with `.value.primary.what`. Do NOT pipe through `fromjson` (it will error with "only strings can be parsed"). The exact key suffix (e.g. `qwen3_6_35b`) varies per install — match with `select(.key | startswith("structured_vlm"))`.

**Important**: that JSON metadata is also fully tokenized into the FTS index. So `q="Claude Code Mastra workspace"` will match a screenshot whose VLM said `app=Claude Code, what="...Mastra...", workspace=...` — even if "Mastra" doesn't appear in the OCR text.

## How to query well

### Strategy 0 — look at raw results before narrowing

Resist the urge to pre-anchor on what you think the user means. A "find 最终幻想" question sounds like it's about the *game*, but the same brand lives across YouTube videos, Bilibili clips, wallpaper engines, wikis, store pages, and game launchers. The user's casual phrasing names the topic, not the surface — only the corpus knows where they actually consumed it.

So run one wide query first and let the results tell you what surfaces exist:

```bash
curl -s --get 'http://127.0.0.1:8839/api/search' \
  --data-urlencode 'q=最终幻想' --data-urlencode 'facet=true' --data-urlencode 'limit=20' > /tmp/raw.json
jq -r '.hits[].document
  | "\(.file_created_at)  \([.metadata_entries[] | select(.key=="active_app") | .value][0] // "?")  \([.metadata_entries[] | select(.key=="url") | .value // "-"][0])  \([.metadata_entries[] | select(.key=="active_window") | .value // "-"][0] | .[0:80])"' /tmp/raw.json
```

Sample output (verified on a real install):

```
2026-04-03T15:26Z  Google Chrome  about:blank                                    (55) When Tifa played「Tifa's T…Rebirth🖤 Ru's Piano - YouTube
2026-04-02T15:47Z  Google Chrome  about:blank                                    (55) Final Fantasy X「To Zanark… Medley | Ru's Piano - YouTube
2026-02-15T15:59Z  Google Chrome  https://www.bilibili.com/video/BV1K2HQzbEAy…  “蒂法的审视 手机动态壁纸 wallpaper engine_哔哩哔哩_bilibili”🔊
2026-01-30T05:17Z  Google Chrome  https://www.bilibili.com/                      哔哩哔哩 (゜-゜)つロ 干杯~-bilibili
```

Now you know: the user doesn't play Final Fantasy — they watch **Ru's Piano** play FF themes on YouTube, and **蒂法的审视 wallpaper engine** clips on Bilibili. If you'd anchored on `q=最终幻想 game` or guessed `app_names=Final Fantasy` you'd have found nothing. The corpus revealed both the surfaces (YouTube + Bilibili) AND the user's actual relationship to the topic (music + wallpapers, not gameplay).

Now you can build **per-surface queries** anchored on each surface's stable identifier and merge the timelines.

**Anchor on stable identifiers, not free-text names**, because free-text is noisy — short or common substrings match the `library_ids=` parameter inside memos's own URL bar, and a CJK brand name often matches OCR'd filenames of unrelated downloaded videos. Stable identifiers come from the URL or the exact app name:

- Website: domain in the URL (`guancha.cn`, `youtube.com/watch?v=…`)
- Bilibili channel: UID in `space.bilibili.com/<uid>` (e.g. `10330740`)
- YouTube channel: handle in URL (`@mastra-ai`, `@RusPiano`)
- App / brand on macOS: exact `active_app` value (`iTerm2`, `Google Chrome`, `企业微信`)

Cross-check every match by filtering hits client-side on the URL or app fields — never trust the FTS hit list alone for "did the user actually visit / consume X" questions. The skill's job is to use multiple raw queries + client-side filtering to give the user a *true* answer, not to take the first FTS rank as gospel.

### Strategy 1 — content keywords first

```bash
curl -s 'http://127.0.0.1:8839/api/search?q=Mastra+roadmap&limit=15' | jq '.hits[].document | {id, filepath, file_created_at}'
```

Joining terms with `+` (URL-encoded space) gives an AND query (jieba splits, then FTS5 does AND-of-tokens). Mix English + Chinese freely: `q=理赔+Demo+演示`.

### Strategy 2 — narrow with app

The user's `active_app` is recorded literally per OS. Common values:
- macOS: `Google Chrome`, `iTerm2`, `Claude`, `Cursor`, `WeChat`, `企业微信`
- Windows: `msedge.exe`, `chrome.exe`, `WeChat.exe`, `claude.exe`

```bash
curl -s 'http://127.0.0.1:8839/api/search?q=mastra+roadmap&app_names=Google+Chrome&limit=10' \
  | jq '.hits[].document | {id, filepath, file_created_at}'
```

### Strategy 3 — narrow with time

Times are UNIX seconds, UTC. Compute with `date`:

```bash
# "last 7 days"
SINCE=$(date -v-7d -u +%s 2>/dev/null || date -d '7 days ago' -u +%s)
NOW=$(date -u +%s)

curl -s "http://127.0.0.1:8839/api/search?q=mastra&start=$SINCE&end=$NOW&limit=20"
```

For specific local dates: parse the user's date words (e.g. "上周三" → resolve to absolute → 00:00 local → UNIX UTC) and use a 1- or 24-hour window.

### Strategy 4 — combine

The fastest path to a precise hit is `q + app + tight time window`. For "find the YouTube Mastra roadmap livestream from last week":

```bash
SINCE=$(date -v-10d -u +%s 2>/dev/null || date -d '10 days ago' -u +%s)
NOW=$(date -u +%s)
curl -s "http://127.0.0.1:8839/api/search?q=mastra+roadmap+youtube&app_names=Google+Chrome&start=$SINCE&end=$NOW&limit=10" > /tmp/hits.json
jq '.hits[].document | {id, filepath, file_created_at}' /tmp/hits.json
```

**Tip**: pipe the response to a tmp file before complex `jq` filters. Inline shell-quoted jq with nested `\"...\"` escapes is fragile — use a file.

### Strategy 5 — facet to discover

When `q` returns hundreds of results, set `facet=true` to see what apps and time range dominate the matches:

```bash
curl -s 'http://127.0.0.1:8839/api/search?q=mastra&facet=true&limit=5' \
  | jq '{date_range, bucket_unit, date_buckets: .date_buckets[:10], facet_counts: .facet_counts[0].counts[:10]}'
```

- **`date_range`** (top-level): `{earliest, latest}` ISO timestamps spanning all matched entities under the current filters. Use it to suggest a tighter `start`/`end` window.
- **`date_buckets`** (top-level): `[{date, count}]` grouped by day or month — the bucket unit is adaptive based on the matched span (≤ 60 days → day, else month). The chosen unit is reported in `bucket_unit`. Single-bucket results are suppressed (returned as empty + `bucket_unit=null`) since they're not useful for narrowing.
- **`facet_counts[0].counts`**: list of `{value, count}` for `active_app`, sorted desc. Use it to suggest an `app_names=` filter, or to ask the user which app they meant.

All three are populated only when `facet=true` (or when `settings.facet=true` server-side).

To drill into a bucket, re-issue with `?date=YYYY-MM` or `?date=YYYY-MM-DD`. The server intersects `date` with the existing filters; if you also set `start`/`end`, the effective range is the overlap. After drilling into a month, the next response's `date_buckets` automatically adapts to days within that month.

## Handling large result sets

`/api/search` caps `limit` at 200 per request, but the response now exposes the real total under filters in the `found` field. Use it directly — no heuristics needed.

### Reading `found` and `out_of`

Every response includes:

```json
{ "found": 2883, "out_of": 1464297, "hits": [ ... 200 items ... ], ... }
```

- **`found`** — unbounded count of FTS matches under your filters (`q`, `start`/`end`, `app_names`, `library_ids`). This is the truthful answer to "how many things matched my keywords?". If `found > limit`, there are more matches you didn't get back.
- **`out_of`** — total entities in the collection scope (`library_ids` only — `q`/`start`/`end`/`app_names` are dropped). Typesense convention: "found N out of M total". Surface this only when the user asks dataset-level questions ("how many screenshots do I have?"); for normal "find X" replies use `found`.

**Edge case**: very rarely, `found < len(hits)` when vector search contributes hits whose FTS rank was zero (e.g. queries with no good keyword match but semantic neighbors). Treat `found` as the keyword-match count, with the understanding that `hits` may include a few extra semantic neighbors.

### Decision flow

```
resp  = search(q, start, end, limit=200)
hits  = resp.hits
found = resp.found

if found <= len(hits):
    return hits                              # complete, done

if user wants "top match" / "first few":
    return hits[:N]                          # top-ranked are already here

if user wants comprehensive scan ("show me everything ..."):
    return time_slice(q, start, end)         # recipe below — still needed (no offset yet)

else:
    tell user: f"{found} matches, narrow with app or shorter time window"
```

### Recipe: time-window slicing

For "show me every screenshot of X in the last week", recursively halve the time window when truncation hits. **Always use a tmp file for the response body** — bash command substitution `$(curl ...)` mangles JSON that contains literal newlines or control chars (which OCR / VLM metadata frequently does).

```bash
# bash function — paste into agent shell or save as ~/bin/pensieve-paged-search.sh
paged_search() {
    local q="$1" start="$2" end="$3"
    local tmp
    tmp=$(mktemp)
    curl -s "http://127.0.0.1:8839/api/search?q=$(echo -n "$q" | jq -sRr @uri)&start=$start&end=$end&limit=200" > "$tmp"
    local n
    n=$(jq '.hits | length' "$tmp")
    if [ "$n" -lt 200 ] || [ $((end - start)) -lt 60 ]; then
        jq -c '.hits[]' "$tmp"
        rm "$tmp"
        return
    fi
    rm "$tmp"
    local mid=$(( (start + end) / 2 ))
    paged_search "$q" "$start" "$mid"
    paged_search "$q" "$mid" "$end"
}

# Usage: collect all 'memos' hits in the last 7 days
SINCE=$(date -v-7d -u +%s 2>/dev/null || date -d '7 days ago' -u +%s)
NOW=$(date -u +%s)
paged_search "memos" "$SINCE" "$NOW" > /tmp/all_hits.ndjson
wc -l /tmp/all_hits.ndjson    # raw hit count (may include boundary dups)
```

**Boundary duplicates**: the `mid` second may match in both halves if multiple captures share that timestamp. Dedupe by `id`:

```bash
jq -s 'unique_by(.document.id)' /tmp/all_hits.ndjson > /tmp/dedup.json
jq 'length' /tmp/dedup.json
```

In testing, a "last 24h" query for `q=memos` produced 2888 raw hits → 2883 unique. Boundary dup rate is small but real.

### Floor: 60-second window

If a 60-second window still saturates 200 hits, the burst is too dense to enumerate (e.g. continuous scrolling capturing every 4 s = 15 captures/min × 5+ apps multiplied = saturation). Stop recursion there and report: "this minute hit the cap; the screen activity was too dense to enumerate, please narrow further".

### When NOT to slice

- Casual lookup → top hits are already most relevant; no slice needed
- User said "first 10" or "best match" → respect that intent, don't expand
- Truncation in a query that already has tight time + app filters → suggest different keywords instead of slicing

## How to interpret results

Order matters — hybrid_search ranks by reciprocal rank fusion of FTS (weight 0.7) + vector embedding similarity (0.3). The top hit is most likely the right one for direct lookups; for "find all" queries, walk all hits.

**Per hit, extract the human-readable summary**. Save to a tmp file first to keep the `jq` filter readable:

```bash
curl -s 'http://127.0.0.1:8839/api/search?q=mastra&limit=10' > /tmp/hits.json

# Per-hit one-liner: timestamp + app + topic + truncated 'what'
jq -r '.hits[].document |
       "\(.file_created_at)  \([.metadata_entries[]
                               | select(.key | startswith("structured_vlm"))
                               | .value.primary
                               | "app=\(.app // "?")  topic=\(.title_or_topic // "?")  what=\((.what // "?")[0:80])"][0])"' /tmp/hits.json
```

Sample output (verified):

```
2026-04-30T01:35:21Z  app=Google Chrome  topic=mastra roadmap  what=在 Google 搜索框中输入并搜索 'mastra roadmap'
2026-04-30T01:35:26Z  app=Google Chrome  topic=mastra roadmap  what=在 Google 搜索框中输入并搜索 'mastra roadmap'
2026-05-03T13:03:00Z  app=iTerm2         topic=Agent 检索       what=在终端内运行 Claude Code 进行代码开发...
```

`primary.what` is in the user's interface language (Chinese for Chinese-locale machines). Don't translate unless asked — show it as-is.

**Timestamp** is `file_created_at` (ISO 8601 UTC). Convert to user-local for display.

## Returning clickable URLs to the user

After every search, return both:

1. **One search-page URL** — same query in the browser, so the user can browse all matches visually
2. **One entity URL per cited hit** — so the user can click to verify a specific screenshot in context

### Building the search-page URL

Mirror the API params, URL-encoded. **Always include both `q` and `submitted_q` with the same value** — `q` populates the search input, `submitted_q` activates the facet sidebar with the right counts. Sharing only `q` leaves the facets blank until the user hits Enter.

`app_names` and `library_ids` use repeated-key style in the web URL (`&app_names=A&app_names=B`); but the route's `z.array(z.coerce.number())` schema also accepts comma-separated.

```bash
# Build a search-page URL for a query
QUERY="mastra roadmap"
SINCE=1746230400
NOW=1746834400
APPS="Google Chrome"

python3 -c "
import urllib.parse
q   = urllib.parse.quote('$QUERY')
app = urllib.parse.quote('$APPS')
print(f'http://127.0.0.1:8839/?q={q}&submitted_q={q}&start=$SINCE&end=$NOW&app_names={app}')
"
# → http://127.0.0.1:8839/?q=mastra%20roadmap&submitted_q=mastra%20roadmap&start=1746230400&end=1746834400&app_names=Google%20Chrome
```

### Building per-entity URLs

```bash
ENTITY_ID=1646223
echo "http://127.0.0.1:8839/entities/$ENTITY_ID"
```

### Standard reply format

When the user asks "find X", reply in roughly this shape:

```markdown
Found **3 of 47 matches** for **mastra roadmap** in the last 7 days:

1. **2026-04-30 09:35 (Google Chrome)** — Searching "mastra roadmap" in Google
   → http://127.0.0.1:8839/entities/1634834

2. **2026-04-30 09:35 (Google Chrome)** — Same search, second frame
   → http://127.0.0.1:8839/entities/1634835

3. **2026-05-03 21:03 (iTerm2)** — Claude Code session discussing agent retrieval for the Mastra livestream
   → http://127.0.0.1:8839/entities/1643716

[See all in browser](http://127.0.0.1:8839/?q=mastra%20roadmap&submitted_q=mastra%20roadmap&start=1746230400&end=1746834400)
```

**Always** include the `[See all in browser](...)` link, even when there's only 1 hit — it lets the user re-run the query and tweak filters without going through you. **Always** include the per-hit `entities/<id>` URL because clicking it opens the full-resolution screenshot with surrounding metadata, far richer than what you can fit in a CLI reply.

**Show `found` when it exceeds returned hits** (e.g. "3 of 47 matches"), so the user knows there's more to browse. If `found == len(hits)`, just say "Found 3 hits ..." without the total. **`out_of` is collection size** (matches Typesense semantics) — surface it only when the user asks "how many screenshots do I have total?" or similar dataset-level questions.

For paginated/sliced results (the `paged_search` recipe earlier), still link to the *unsliced* search page URL — the user wants to browse, not to see your slicing internals.

## Detecting + filling structured_vlm gaps

**Why this matters**: search quality depends on the `structured_vlm_v1_*` metadata field on each entity. That field is what holds `primary.app` / `primary.what` / `primary.workspace` — the LLM-readable summary that makes "find Mastra roadmap" work even when "Mastra" isn't visible in the OCR text. Entities lacking this field only have OCR; their search relevance is much lower.

Two sources of gaps:

1. **Pre-rollout entities**: screenshots captured before structured_vlm was running on the user's machine. Easy to recognize — entire days will be 100% missing.
2. **Transient failures**: VLM endpoint was down / rate-limited / image broken. Sparse — typically <1% of a day.

The plugin pipeline is idempotent and re-runnable, so backfilling is safe.

### Step 1 — Discover the structured_vlm plugin id

```bash
curl -s http://127.0.0.1:8839/api/plugins | jq '.[] | select(.name == "builtin_structured_vlm") | .id'
# → 3   (varies per install)
```

### Step 2 — Find the library + folder for the screenshots dir

A user can have multiple libraries (test imports, archives). The "live" one is named per `default_library` in config:

```bash
DEFAULT_LIB_NAME=$(curl -s http://127.0.0.1:8839/api/config | jq -r '.default_library')
curl -s http://127.0.0.1:8839/api/libraries \
  | jq --arg n "$DEFAULT_LIB_NAME" '.[] | select(.name == $n) | {id, folders: [.folders[] | {id, path}]}'
# → {"id": 6, "folders": [{"id": 14, "path": "/Users/.../.memos/screenshots"}]}
```

Capture `LIB` and `FOLDER` ids and the `screenshots_root` path for use below.

### Step 3 — Gap audit per day

Walk a day's entities, count those missing `structured_vlm` in `plugin_status`. Use a tmp dir for the JSON bodies (same control-char gotcha as in pagination).

```bash
LIB=6; FOLDER=14; PLUGIN=3
SCREENSHOTS_ROOT="$HOME/.memos/screenshots"
DAY=20260401
TMPDIR=$(mktemp -d)

audit_day() {
    local day="$1"
    local has=0 miss=0 offset=0
    while :; do
        curl -s "http://127.0.0.1:8839/api/libraries/$LIB/folders/$FOLDER/entities?limit=400&offset=$offset&path_prefix=$SCREENSHOTS_ROOT/$day" > "$TMPDIR/batch.json"
        local n
        n=$(jq 'length' "$TMPDIR/batch.json")
        [ "$n" -eq 0 ] && break
        local h
        h=$(jq "[.[] | select(.plugin_status | map(.plugin_id) | index($PLUGIN))] | length" "$TMPDIR/batch.json")
        has=$((has + h))
        miss=$((miss + n - h))
        offset=$((offset + n))
        [ "$n" -lt 400 ] && break
    done
    echo "$day total=$((has + miss)) has=$has missing=$miss"
}

audit_day "$DAY"
# Sample real output:
#   20260101 total=2051 has=0    missing=2051   ← all pre-rollout
#   20260401 total=3817 has=3783 missing=34     ← post-rollout, transient gaps
#   20260424 total=3835 has=3835 missing=0      ← clean

rm -rf "$TMPDIR"
```

To audit a range of days, just loop:

```bash
for d in 20260401 20260402 20260403; do audit_day "$d"; done
```

### Step 4 — List the missing entity ids on a day (optional)

If the user wants to know exactly which entities are missing:

```bash
LIB=6; FOLDER=14; PLUGIN=3
DAY=20260401
TMPDIR=$(mktemp -d)
> "$TMPDIR/missing.txt"
offset=0
while :; do
    curl -s "http://127.0.0.1:8839/api/libraries/$LIB/folders/$FOLDER/entities?limit=400&offset=$offset&path_prefix=$HOME/.memos/screenshots/$DAY" > "$TMPDIR/batch.json"
    n=$(jq 'length' "$TMPDIR/batch.json")
    [ "$n" -eq 0 ] && break
    jq -r ".[] | select((.plugin_status | map(.plugin_id) | index($PLUGIN)) == null) | \"\(.id) \(.filepath)\"" "$TMPDIR/batch.json" >> "$TMPDIR/missing.txt"
    offset=$((offset + n))
    [ "$n" -lt 400 ] && break
done
wc -l "$TMPDIR/missing.txt"
head "$TMPDIR/missing.txt"
```

### Step 5 — Run scan to fill gaps

`memos scan <PATH> --plugin <PLUGIN_ID>` walks the directory, checks each file's plugin_status, and triggers the structured_vlm webhook only for entities missing that plugin (idempotent — already-processed entities are skipped).

```bash
# Backfill one day's structured_vlm
memos scan "$HOME/.memos/screenshots/20260401" --plugin 3 -bs 4
```

`-bs 4` (batch-size 4) is a good balance — high enough to keep the VLM endpoint busy, low enough to recover gracefully if a batch fails. The default `-bs 1` is too slow for whole-day backfills.

**Warn the user about cost first**:

- A pre-rollout day with ~3000 missing entities at ~5–10 s per image = **20–60 min** of VLM time, plus token cost
- For a local Ollama / vLLM endpoint, only time cost
- For a paid API, also `tokens × $price/1M` × 3000

Quote the estimate before running. Don't auto-trigger backfill of multiple days without explicit "yes, do all of them".

### Step 6 — Verify after scan

Re-run the audit (Step 3) for the day. `missing` should be near 0. If it's still high, the VLM endpoint may be unreachable or returning errors — check `~/.memos/logs/` for `structured_vlm` failure-category lines.

### When to use this proactively

- **Search returned hits with weak `primary.what`** (or no `structured_vlm_v1_*` metadata at all): tell the user "these look like pre-rollout / failed entities; want me to backfill the day?"
- **A specific date the user keeps mentioning has no good results**: audit it first, propose backfill if missing > 20%.
- **The user asks "why does search miss X?"**: gap audit on the date they expect, often the answer.

### What this skill won't auto-decide

Don't trigger backfill silently. **Always show the audit numbers + cost estimate first**, get explicit user confirmation, then run.

## Opening a screenshot

The `filepath` is an absolute local path. To show the user the actual image:

```bash
# macOS
open "/Users/.../screenshots/20260423/00001.webp"

# Linux
xdg-open "/path/to/file.webp"

# Windows (PowerShell)
Start-Process "C:\path\to\file.webp"
```

Don't open more than 2-3 at a time — overwhelming. Pick the top hit, show its timestamp + `primary.what`, and ask if user wants more.

## Common pitfalls

1. **Empty `q=""` returns recent files unranked** — that's `crud.list_entities` behavior, not search. If user says "find the latest X", do `q=X` not `q=""`.
2. **`file_type_group='image'` is hardcoded server-side** — the index only contains screenshots. Don't expect to find logs / docs.
3. **`active_app` is the OS-reported app, not the logical product**. iTerm2 running Claude Code reports `active_app=iTerm2`. The logical product (e.g. `"Claude Code"`) lives in `structured_vlm.primary.app`. So:
   - To find "any iTerm2 screenshots": `app_names=iTerm2`
   - To find "Claude Code sessions": prefer `q=Claude+Code` (FTS hits structured_vlm metadata) over `app_names`.
4. **Spinner artifacts**: Claude Code's window title cycles `✳`, `⠐`, etc. Don't include spinner glyphs in `q`. Just use the task description text.
5. **Unicode in `q`**: URL-encode Chinese / emoji properly. `curl --data-urlencode 'q=...' -G ...` is safest.
6. **Rate limit**: there isn't one, but each query also hits the embedding model for vector search. Don't burst > 20 queries in a tight loop without batching.
7. **Old data without VLM**: screenshots predating structured_vlm rollout (or where VLM failed) only have OCR text. Their hits will lack the `structured_vlm_v1_*` entry — fall back to `ocr_result` for context.
8. **`ocr_result` is not in search hits** — it's stripped from `/api/search` responses to keep them small (the full payload is ~15 KB per entry × 48 hits). The other metadata (timestamp, active_app, active_window, url, structured_vlm_*) is intact. If you genuinely need the OCR text for a specific entity, fetch `/api/entities/{id}` directly.
9. **Chinese FTS noise is real**: the PG index uses jieba word segmentation, so a multi-character Chinese phrase gets split into smaller tokens. Common single-character morphemes (`网` / `站` / `中` etc.) match a lot of unrelated OCR (网络 / 网站 / 网址), so FTS will surface low-relevance hits mixed with the real ones. Hybrid RRF mitigates this somewhat via vector search, but for Chinese brand / site names always cross-check hits with URL or `active_app` filters (see Strategy 0) — don't trust the FTS rank alone.

## When to give up and ask

- **0 hits**: try variations (synonyms, broader date range, drop `app_names`). After 3 variations, ask user for more context ("do you remember which app?").
- **`found > limit`**: see "Handling large result sets" above. Default action depends on user intent — narrow query for casual lookup, time-slice for comprehensive scans. (P1 will add an offset parameter so the time-slice recipe can retire.)
- **Server returns 5xx**: server-side error, capture body, ask user to check `memos` logs.

## What this skill does NOT do

- ❌ Aggregate stats across days (use future "memos day" / cross-day analytics tools).
- ❌ Find "everything I did on project X this week" — that needs the unfinished Activity / Session aggregation. For now, do a tight `q=X` + time window and let the user scrub.
- ❌ Edit / delete entities. Read-only.
