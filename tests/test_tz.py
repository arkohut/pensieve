from datetime import datetime, timedelta
import pytest

from memos.tz_utils import (
    local_date_to_utc_range,
    utc_ts_to_local_dt,
    local_ts_to_utc,
    LocalOffset,
)

UTC8 = LocalOffset.from_string("+08:00")


def test_local_date_to_utc_range_china():
    """Local 2026-04-17 (UTC+8) maps to UTC [2026-04-16 16:00, 2026-04-17 16:00)."""
    start, end = local_date_to_utc_range("20260417", UTC8)
    assert start == "20260416-160000"
    assert end == "20260417-160000"


def test_utc_to_local_china():
    """UTC 20260417-064639 = Local 20260417-144639 in UTC+8."""
    local_dt = utc_ts_to_local_dt("20260417-064639", UTC8)
    assert local_dt.strftime("%Y%m%d-%H%M%S") == "20260417-144639"


def test_local_to_utc_round_trip():
    """Local->UTC->local should be identity."""
    local_str = "20260417-144639"
    utc_str = local_ts_to_utc(local_str, UTC8)
    back_local = utc_ts_to_local_dt(utc_str, UTC8)
    assert back_local.strftime("%Y%m%d-%H%M%S") == local_str


def test_offset_parse_and_format():
    """Offset accepts +HH:MM and -HH:MM strings."""
    assert LocalOffset.from_string("+08:00").seconds == 8 * 3600
    assert LocalOffset.from_string("-05:30").seconds == -(5 * 3600 + 30 * 60)
    assert LocalOffset.from_string("+08:00").to_string() == "+08:00"


def test_offset_from_system():
    """LocalOffset.from_system() returns the running machine's offset, not a hardcoded value."""
    offset = LocalOffset.from_system()
    # We don't assert a specific value (depends on test machine), but it must be a valid offset
    assert -14 * 3600 <= offset.seconds <= 14 * 3600
