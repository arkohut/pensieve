"""Timezone helpers for converting between UTC (DB storage) and local time (UI/worklog)."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class LocalOffset:
    """Local TZ offset in seconds from UTC. Positive for east of UTC."""
    seconds: int

    @classmethod
    def from_string(cls, s: str) -> "LocalOffset":
        """Parse '+HH:MM' or '-HH:MM' into LocalOffset."""
        sign = 1 if s[0] == "+" else -1
        hours, minutes = s[1:].split(":")
        return cls(sign * (int(hours) * 3600 + int(minutes) * 60))

    @classmethod
    def from_system(cls) -> "LocalOffset":
        """Read the local TZ offset from the OS at call time.

        Uses the current offset (including DST if active), not the standard-time
        offset. This matters for users in DST regions — Task 6's backfill CLI
        converts 'last N days local' to a UTC range and must use the offset that
        was in effect at that moment.
        """
        return cls(int(datetime.now().astimezone().utcoffset().total_seconds()))

    def to_string(self) -> str:
        sign = "+" if self.seconds >= 0 else "-"
        total = abs(self.seconds)
        return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def local_date_to_utc_range(local_date_str: str, offset: LocalOffset) -> tuple[str, str]:
    """Given a local date YYYYMMDD, return the UTC [start, end) range as YYYYMMDD-HHMMSS strings."""
    local_start = datetime.strptime(local_date_str, "%Y%m%d")
    utc_start = local_start - timedelta(seconds=offset.seconds)
    utc_end = utc_start + timedelta(days=1)
    return utc_start.strftime("%Y%m%d-%H%M%S"), utc_end.strftime("%Y%m%d-%H%M%S")


def utc_ts_to_local_dt(ts_str: str, offset: LocalOffset) -> datetime:
    """Parse a UTC timestamp and return local datetime."""
    utc = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
    return utc + timedelta(seconds=offset.seconds)


def local_ts_to_utc(ts_str: str, offset: LocalOffset) -> str:
    """Parse a local timestamp and return UTC string."""
    local = datetime.strptime(ts_str, "%Y%m%d-%H%M%S")
    utc = local - timedelta(seconds=offset.seconds)
    return utc.strftime("%Y%m%d-%H%M%S")
