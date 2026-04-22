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
