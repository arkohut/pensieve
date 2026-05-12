"""Server-level wiring test: /api/search must populate `found` from
count_full_text_matches (or crud.count_entities for q='') and `out_of` from
crud.count_entities with collection scope only (drops q/start/end/app_names).

Uses FastAPI TestClient with a fake search provider — no DB needed."""
from fastapi.testclient import TestClient

import memos.server as server_mod
from memos.server import app


def _reset_collection_cache():
    server_mod._collection_size_cache.clear()


class FakeProvider:
    """Stand-in for SearchProvider that records calls and returns canned data."""

    def __init__(self):
        self.last_count_args = None
        self.canned_total = 0
        self.canned_ids = []

    def hybrid_search(
        self,
        query,
        db,
        limit,
        library_ids=None,
        start=None,
        end=None,
        app_names=None,
        phase_ms=None,
    ):
        return self.canned_ids

    def count_full_text_matches(
        self, query, db, library_ids=None, start=None, end=None, app_names=None
    ):
        self.last_count_args = {
            "query": query,
            "library_ids": library_ids,
            "start": start,
            "end": end,
            "app_names": app_names,
        }
        return self.canned_total

    def get_search_stats(
        self, query, db, library_ids=None, start=None, end=None, app_names=None
    ):
        # Server reads `found` from here when use_facet is on, skipping the
        # separate count call. Record args under the same shape as count so
        # the test asserts the filter inputs reach whichever path runs.
        self.last_count_args = {
            "query": query,
            "library_ids": library_ids,
            "start": start,
            "end": end,
            "app_names": app_names,
        }
        return {"total": self.canned_total, "sampled": False}


def test_found_reflects_total_matches_out_of_reflects_collection(monkeypatch):
    _reset_collection_cache()
    fake = FakeProvider()
    fake.canned_ids = [1, 2, 3]      # only 3 returned
    fake.canned_total = 847          # but 847 actually match the keyword

    monkeypatch.setattr(app.state, "search_provider", fake)

    monkeypatch.setattr(server_mod.crud, "find_entities_by_ids", lambda ids, db: [])

    # count_entities is called for collection_size (out_of). Record args to verify
    # the out_of count drops q / start / end / app_names but keeps library_ids.
    count_calls = []

    def fake_count(db, library_ids=None, start=None, end=None):
        count_calls.append(
            {"library_ids": library_ids, "start": start, "end": end}
        )
        return 1234567  # collection size

    monkeypatch.setattr(server_mod.crud, "count_entities", fake_count)

    client = TestClient(app)
    resp = client.get(
        "/api/search",
        params={
            "q": "mastra",
            "limit": 10,
            "start": 1700000000,
            "end": 1700100000,
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] == 847, "found must equal total FTS matches under active filters"
    assert body["out_of"] == 1234567, "out_of must equal collection size, ignoring q/start/end"
    # The FTS count was called with the same filters as the search
    assert fake.last_count_args["query"] == "mastra"
    assert fake.last_count_args["start"] == 1700000000
    # crud.count_entities for out_of was called WITHOUT start/end (collection scope)
    assert count_calls == [{"library_ids": None, "start": None, "end": None}]


def test_empty_query_uses_count_entities_for_both_fields(monkeypatch):
    """When q='', server uses crud.count_entities twice:
    - once with filters → found
    - once without filters → out_of (via cache helper)"""
    _reset_collection_cache()
    fake = FakeProvider()
    monkeypatch.setattr(app.state, "search_provider", fake)

    monkeypatch.setattr(server_mod.crud, "list_entities", lambda **kw: [])

    # Two distinct return values keyed by whether time filters are present
    def fake_count(db, library_ids=None, start=None, end=None):
        if start is not None or end is not None:
            return 12345  # filtered: matches "found"
        return 999999  # unfiltered: matches "out_of"

    monkeypatch.setattr(server_mod.crud, "count_entities", fake_count)

    client = TestClient(app)
    resp = client.get(
        "/api/search",
        params={
            "q": "",
            "limit": 5,
            "start": 1700000000,
            "end": 1700100000,
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] == 12345
    assert body["out_of"] == 999999
    # count_full_text_matches must NOT be called for empty q
    assert fake.last_count_args is None


def test_collection_size_is_cached_across_requests(monkeypatch):
    """The collection-size COUNT(*) is expensive on multi-million-row tables.
    Within the TTL, repeated /api/search requests must reuse the cached value."""
    _reset_collection_cache()
    fake = FakeProvider()
    fake.canned_total = 5
    monkeypatch.setattr(app.state, "search_provider", fake)
    monkeypatch.setattr(server_mod.crud, "find_entities_by_ids", lambda ids, db: [])

    # Track every call to crud.count_entities — without the cache, each request
    # would invoke it once for out_of (q!=''); we expect a single invocation
    # across many requests.
    call_count = {"n": 0}

    def fake_count(db, library_ids=None, start=None, end=None):
        call_count["n"] += 1
        return 1_000_000

    monkeypatch.setattr(server_mod.crud, "count_entities", fake_count)

    client = TestClient(app)
    for _ in range(5):
        resp = client.get("/api/search", params={"q": "x", "limit": 1})
        assert resp.status_code == 200
        assert resp.json()["out_of"] == 1_000_000

    assert call_count["n"] == 1, f"expected cache to coalesce 5 requests into 1 count, got {call_count['n']}"


def test_hybrid_search_and_stats_run_in_parallel(monkeypatch):
    """hybrid_search and get_search_stats are independent — they must run
    concurrently (use_facet path) so total wall time is max(search, stats)
    rather than the sum."""
    import time as _time

    _reset_collection_cache()

    class SlowProvider:
        def __init__(self):
            self.search_window = []
            self.stats_window = []

        def hybrid_search(self, query, db, limit, **kw):
            self.search_window.append(_time.monotonic())
            _time.sleep(0.3)
            self.search_window.append(_time.monotonic())
            return []

        def count_full_text_matches(self, query, db, **kw):
            return 0

        def get_search_stats(self, query, db, **kw):
            self.stats_window.append(_time.monotonic())
            _time.sleep(0.3)
            self.stats_window.append(_time.monotonic())
            return {"total": 0, "sampled": False}

    fake = SlowProvider()
    monkeypatch.setattr(app.state, "search_provider", fake)
    monkeypatch.setattr(server_mod.crud, "find_entities_by_ids", lambda ids, db: [])
    monkeypatch.setattr(server_mod.crud, "count_entities", lambda **kw: 1)

    client = TestClient(app)
    t0 = _time.monotonic()
    resp = client.get("/api/search", params={"q": "x", "limit": 1, "facet": "true"})
    elapsed = _time.monotonic() - t0

    assert resp.status_code == 200
    # Sequential would be ≥ 0.6s; parallel should be ≈ 0.3s. 0.5s ceiling
    # proves we're not running serially.
    assert elapsed < 0.5, f"expected parallel execution (~0.3s), got {elapsed:.2f}s"
    s_start, s_end = fake.search_window
    st_start, st_end = fake.stats_window
    overlap = min(s_end, st_end) - max(s_start, st_start)
    assert overlap > 0, "hybrid_search and get_search_stats windows did not overlap"


def test_collection_size_cache_keys_by_library_ids(monkeypatch):
    """Different library_ids must not share the cache."""
    _reset_collection_cache()
    fake = FakeProvider()
    fake.canned_total = 5
    monkeypatch.setattr(app.state, "search_provider", fake)
    monkeypatch.setattr(server_mod.crud, "find_entities_by_ids", lambda ids, db: [])

    seen_keys = []

    def fake_count(db, library_ids=None, start=None, end=None):
        key = tuple(sorted(library_ids)) if library_ids else None
        seen_keys.append(key)
        return {None: 999, (1,): 100, (2,): 200}[key]

    monkeypatch.setattr(server_mod.crud, "count_entities", fake_count)

    client = TestClient(app)
    r1 = client.get("/api/search", params={"q": "x", "limit": 1})
    r2 = client.get("/api/search", params={"q": "x", "limit": 1, "library_ids": "1"})
    r3 = client.get("/api/search", params={"q": "x", "limit": 1, "library_ids": "2"})
    # repeats — should hit cache
    r1b = client.get("/api/search", params={"q": "x", "limit": 1})
    r2b = client.get("/api/search", params={"q": "x", "limit": 1, "library_ids": "1"})

    assert r1.json()["out_of"] == 999
    assert r2.json()["out_of"] == 100
    assert r3.json()["out_of"] == 200
    assert r1b.json()["out_of"] == 999
    assert r2b.json()["out_of"] == 100
    # 3 distinct keys → 3 DB calls; r1b/r2b are cache hits
    assert seen_keys == [None, (1,), (2,)], f"unexpected DB calls: {seen_keys}"
