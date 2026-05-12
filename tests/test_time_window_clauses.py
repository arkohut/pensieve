"""Unit tests for the search _time_window_clauses helper.

Before this helper, every callsite gated the time filter on
`start is not None and end is not None`, so a half-open window (e.g. user
picked only 'from' in the custom date picker) silently dropped the filter
and the query scanned the full index.
"""
from memos.search import _time_window_clauses


def test_no_bounds_returns_empty():
    params: dict = {}
    assert _time_window_clauses("col", None, None, params) == []
    assert params == {}


def test_only_start_applies_lower_bound():
    params: dict = {}
    clauses = _time_window_clauses("col", 100, None, params)
    assert clauses == ["col >= :start"]
    assert params == {"start": 100}


def test_only_end_applies_upper_bound():
    params: dict = {}
    clauses = _time_window_clauses("col", None, 200, params)
    assert clauses == ["col <= :end"]
    assert params == {"end": 200}


def test_both_bounds_apply_both_clauses():
    params: dict = {}
    clauses = _time_window_clauses("col", 100, 200, params)
    assert clauses == ["col >= :start", "col <= :end"]
    assert params == {"start": 100, "end": 200}


def test_column_expression_is_interpolated():
    params: dict = {}
    clauses = _time_window_clauses(
        "EXTRACT(EPOCH FROM e.file_created_at)", 100, 200, params
    )
    assert clauses == [
        "EXTRACT(EPOCH FROM e.file_created_at) >= :start",
        "EXTRACT(EPOCH FROM e.file_created_at) <= :end",
    ]


def test_existing_params_preserved():
    params = {"query": "memos"}
    _time_window_clauses("col", 100, 200, params)
    assert params == {"query": "memos", "start": 100, "end": 200}
