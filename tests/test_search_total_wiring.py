"""Server-level wiring test: /api/search must populate `found` from
count_full_text_matches (or crud.count_entities for q='') and `out_of` from
crud.count_entities with collection scope only (drops q/start/end/app_names).

Uses FastAPI TestClient with a fake search provider — no DB needed."""
from fastapi.testclient import TestClient

from memos.server import app


class FakeProvider:
    """Stand-in for SearchProvider that records calls and returns canned data."""

    def __init__(self):
        self.last_count_args = None
        self.canned_total = 0
        self.canned_ids = []

    def hybrid_search(
        self, query, db, limit, library_ids=None, start=None, end=None, app_names=None
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

    def get_search_stats(self, *a, **k):
        return {}


def test_found_reflects_total_matches_out_of_reflects_collection(monkeypatch):
    fake = FakeProvider()
    fake.canned_ids = [1, 2, 3]      # only 3 returned
    fake.canned_total = 847          # but 847 actually match the keyword

    monkeypatch.setattr(app.state, "search_provider", fake)

    import memos.server as server_mod
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
    - once without filters → out_of"""
    fake = FakeProvider()
    monkeypatch.setattr(app.state, "search_provider", fake)

    import memos.server as server_mod
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
