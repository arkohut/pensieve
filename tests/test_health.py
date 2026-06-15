import time
import memos.health as health


def test_touch_and_age_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(health, "heartbeat_path", lambda: tmp_path / "record.heartbeat")
    assert health.heartbeat_age() is None  # no file yet
    health.touch_heartbeat()
    age = health.heartbeat_age(now=time.time() + 10)
    assert 9.0 <= age <= 11.0


def test_stale_threshold_uses_floor(monkeypatch):
    # record_interval=4 * factor=5 = 20, but the floor is 120 -> 120
    monkeypatch.setattr(health.settings, "record_interval", 4)
    monkeypatch.setattr(health.settings.health, "heartbeat_stale_factor", 5)
    monkeypatch.setattr(health.settings.health, "heartbeat_stale_min_seconds", 120)
    assert health.stale_threshold() == 120


def test_stale_threshold_scales_above_floor(monkeypatch):
    monkeypatch.setattr(health.settings, "record_interval", 60)
    monkeypatch.setattr(health.settings.health, "heartbeat_stale_factor", 5)
    monkeypatch.setattr(health.settings.health, "heartbeat_stale_min_seconds", 120)
    assert health.stale_threshold() == 300
