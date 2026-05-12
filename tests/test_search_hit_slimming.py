"""Predicate-level test for the search-hit metadata filter.

Only `ocr_result` is excluded — it's the only key heavy enough to bloat the
response. Smaller plugin outputs (structured_vlm_*, *_result) stay in hits
so downstream callers (UI grid, pensieve-search skill) can read them.
"""
from memos.server import _is_search_hit_excluded


def test_excludes_ocr_result():
    assert _is_search_hit_excluded("ocr_result")


def test_keeps_structured_vlm():
    assert not _is_search_hit_excluded("structured_vlm_v1_qwen3_6_35b")
    assert not _is_search_hit_excluded("structured_vlm_v2_anything")


def test_keeps_vlm_model_results():
    for k in (
        "minicpm_v_result",
        "minicpm_v_2.6_result",
        "qwen2.5_vl_32b_result",
        "qwen3.5_35b_result",
        "pixtral_large_instruct_2411_result",
    ):
        assert not _is_search_hit_excluded(k), k


def test_keeps_lightweight_keys():
    for k in (
        "timestamp",
        "active_app",
        "active_window",
        "screen_name",
        "sequence",
        "url",
        "tags",
    ):
        assert not _is_search_hit_excluded(k), k
