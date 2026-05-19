"""Tests for memos.utils.watch_state predicates."""
import os
from unittest.mock import patch

import pytest

from memos.utils import watch_state


class TestIsAlive:
    def test_returns_false_when_no_pid_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: tmp_path / "missing.pid")
        assert watch_state.is_alive() is False

    def test_returns_false_when_pid_file_empty(self, tmp_path, monkeypatch):
        pid_path = tmp_path / "watch.pid"
        pid_path.write_text("")
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: pid_path)
        assert watch_state.is_alive() is False

    def test_returns_false_for_dead_pid(self, tmp_path, monkeypatch):
        pid_path = tmp_path / "watch.pid"
        pid_path.write_text("999999")
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: pid_path)
        assert watch_state.is_alive() is False

    def test_returns_true_for_own_process(self, tmp_path, monkeypatch):
        pid_path = tmp_path / "watch.pid"
        pid_path.write_text(str(os.getpid()))
        monkeypatch.setattr(watch_state, "_pid_file_path", lambda: pid_path)
        assert watch_state.is_alive() is True


class TestIsOnBattery:
    def test_returns_false_when_no_battery(self):
        with patch("memos.utils.watch_state.psutil.sensors_battery", return_value=None):
            assert watch_state.is_on_battery() is False

    def test_returns_true_when_unplugged(self):
        class FakeBattery:
            power_plugged = False
        with patch("memos.utils.watch_state.psutil.sensors_battery", return_value=FakeBattery()):
            assert watch_state.is_on_battery() is True

    def test_returns_false_when_plugged(self):
        class FakeBattery:
            power_plugged = True
        with patch("memos.utils.watch_state.psutil.sensors_battery", return_value=FakeBattery()):
            assert watch_state.is_on_battery() is False


class TestIsWithinIdleWindow:
    def test_same_day_window_inside(self):
        assert watch_state.is_within_idle_window(("08:00", "18:00"), now_hhmm="12:00") is True

    def test_same_day_window_outside(self):
        assert watch_state.is_within_idle_window(("08:00", "18:00"), now_hhmm="20:00") is False

    def test_crosses_midnight_inside_after_start(self):
        assert watch_state.is_within_idle_window(("22:00", "06:00"), now_hhmm="23:00") is True

    def test_crosses_midnight_inside_before_end(self):
        assert watch_state.is_within_idle_window(("22:00", "06:00"), now_hhmm="04:00") is True

    def test_crosses_midnight_outside(self):
        assert watch_state.is_within_idle_window(("22:00", "06:00"), now_hhmm="12:00") is False

    def test_full_day_window(self):
        assert watch_state.is_within_idle_window(("00:00", "23:59"), now_hhmm="03:14") is True
