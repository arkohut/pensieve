"""Unit tests for the per-provider _build_fts_filters helpers.

These helpers used to be inlined 3x per provider; we extract them to keep
filter-assembly logic in one place. The tests assert the exact SQL fragments
and param dict for representative input combinations, so future edits can't
silently change the WHERE clause shape that the indexed corpus expects.
"""
import pytest

from memos.search import PostgreSQLSearchProvider, SqliteSearchProvider


_sqlite_has_helper = hasattr(SqliteSearchProvider, "_build_fts_filters")
sqlite_only = pytest.mark.skipif(
    not _sqlite_has_helper,
    reason="SqliteSearchProvider._build_fts_filters lands in the SQLite commit",
)


# --- PG -----------------------------------------------------------------

@pytest.fixture
def pg_provider():
    return PostgreSQLSearchProvider()


def test_pg_no_filters_emits_only_file_type_group(pg_provider):
    where, params, bindparams = pg_provider._build_fts_filters(
        "memos", None, None, None, None
    )
    assert where == ["e.file_type_group = 'image'"]
    assert params == {"query": "memos"}
    assert bindparams == []


def test_pg_library_ids_appends_any_clause(pg_provider):
    where, params, _ = pg_provider._build_fts_filters(
        "memos", [1, 2, 3], None, None, None
    )
    assert "e.library_id = ANY(:library_ids)" in where
    assert params["library_ids"] == [1, 2, 3]


def test_pg_start_only_emits_half_open_lower_bound(pg_provider):
    where, params, _ = pg_provider._build_fts_filters(
        "memos", None, 1000, None, None
    )
    assert "EXTRACT(EPOCH FROM e.file_created_at) >= :start" in where
    assert all(":end" not in c for c in where)
    assert params["start"] == 1000
    assert "end" not in params


def test_pg_end_only_emits_half_open_upper_bound(pg_provider):
    where, params, _ = pg_provider._build_fts_filters(
        "memos", None, None, 2000, None
    )
    assert "EXTRACT(EPOCH FROM e.file_created_at) <= :end" in where
    assert all(":start" not in c for c in where)
    assert params["end"] == 2000


def test_pg_app_names_emits_exists_subquery(pg_provider):
    where, params, _ = pg_provider._build_fts_filters(
        "memos", None, None, None, ["iTerm2", "Google Chrome"]
    )
    app_clause = next(c for c in where if "EXISTS" in c)
    assert "metadata_entries" in app_clause
    assert "me.key = 'active_app'" in app_clause
    assert "me.value = ANY(:app_names)" in app_clause
    assert params["app_names"] == ["iTerm2", "Google Chrome"]


def test_pg_all_filters_combined(pg_provider):
    where, params, _ = pg_provider._build_fts_filters(
        "mastra roadmap", [6], 1000, 2000, ["iTerm2"]
    )
    # Order matters for predictable WHERE assembly: file_type_group, library,
    # time (each bound), app.
    assert where[0] == "e.file_type_group = 'image'"
    assert any("library_id" in c for c in where[1:])
    assert sum(":start" in c for c in where) == 1
    assert sum(":end" in c for c in where) == 1
    assert any("EXISTS" in c for c in where)
    assert set(params) == {"query", "library_ids", "start", "end", "app_names"}


def test_pg_query_is_jieba_segmented(pg_provider):
    # PG's 'simple' tokenizer can't split CJK; we pre-segment so the bound
    # query matches the same tokens that the index was built from.
    _, params, _ = pg_provider._build_fts_filters("观察者网", None, None, None, None)
    # jieba splits 观察者网 → "观察者 网"; the exact split depends on jieba's
    # internal dict, so we just assert it inserted whitespace somewhere.
    assert " " in params["query"]


# --- SQLite -------------------------------------------------------------

@pytest.fixture
def sqlite_provider():
    return SqliteSearchProvider()


@sqlite_only
def test_sqlite_no_filters(sqlite_provider):
    where, params, bindparams = sqlite_provider._build_fts_filters(
        "memos", None, None, None, None
    )
    assert where == ["e.file_type_group = 'image'"]
    assert params == {"query": "memos"}
    assert bindparams == []


@sqlite_only
def test_sqlite_library_ids_uses_in_with_expanding_bindparam(sqlite_provider):
    where, params, bindparams = sqlite_provider._build_fts_filters(
        "memos", [1, 2, 3], None, None, None
    )
    assert "e.library_id IN :library_ids" in where
    assert params["library_ids"] == (1, 2, 3)
    assert any(bp.key == "library_ids" and bp.expanding for bp in bindparams)


@sqlite_only
def test_sqlite_time_uses_strftime_column(sqlite_provider):
    where, params, _ = sqlite_provider._build_fts_filters(
        "memos", None, 1000, 2000, None
    )
    time_clauses = [c for c in where if "strftime" in c]
    assert len(time_clauses) == 2
    assert any(":start" in c for c in time_clauses)
    assert any(":end" in c for c in time_clauses)


@sqlite_only
def test_sqlite_app_names_uses_in_with_expanding_bindparam(sqlite_provider):
    where, params, bindparams = sqlite_provider._build_fts_filters(
        "memos", None, None, None, ["iTerm2"]
    )
    app_clause = next(c for c in where if "EXISTS" in c)
    assert "me.value IN :app_names" in app_clause
    assert params["app_names"] == ("iTerm2",)
    assert any(bp.key == "app_names" and bp.expanding for bp in bindparams)


@sqlite_only
def test_sqlite_query_uses_and_words(sqlite_provider):
    # SQLite's jieba_query() extension does the segmentation, so the helper
    # only needs to and_words-join multi-token input.
    _, params, _ = sqlite_provider._build_fts_filters(
        "mastra roadmap", None, None, None, None
    )
    assert params["query"] == "mastra AND roadmap"
