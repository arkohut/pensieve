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


def test_seconds_since_wake_parses_sysctl(monkeypatch):
    monkeypatch.setattr(health.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        health.subprocess,
        "check_output",
        lambda *a, **k: "{ sec = 1000, usec = 0 } Thu Jan  1 ...\n",
    )
    assert health.seconds_since_wake(now=1100.0) == 100.0


def test_seconds_since_wake_none_off_darwin(monkeypatch):
    monkeypatch.setattr(health.platform, "system", lambda: "Linux")
    assert health.seconds_since_wake() is None


def test_seconds_since_wake_none_on_error(monkeypatch):
    monkeypatch.setattr(health.platform, "system", lambda: "Darwin")
    def boom(*a, **k):
        raise OSError("no sysctl")
    monkeypatch.setattr(health.subprocess, "check_output", boom)
    assert health.seconds_since_wake() is None


def test_screen_recording_ok_true_off_darwin(monkeypatch):
    monkeypatch.setattr(health.platform, "system", lambda: "Linux")
    assert health.screen_recording_ok() is True


def test_base_dir_writable_true(tmp_path, monkeypatch):
    monkeypatch.setattr(health, "_base_dir", lambda: tmp_path)
    assert health.base_dir_writable() is True


def test_base_dir_writable_false_when_probe_raises(monkeypatch):
    class Bad:
        def mkdir(self, *a, **k):
            raise OSError("disk full")
    monkeypatch.setattr(health, "_base_dir", lambda: Bad())
    assert health.base_dir_writable() is False


def _stub_health(monkeypatch, *, ups, age, threshold=120.0, since_wake=9999.0,
                 sr_ok=True, writable=True, stopped=()):
    monkeypatch.setattr(health, "is_service_running", lambda s, **k: (ups.get(s, True), 1))
    monkeypatch.setattr(health, "is_intentionally_stopped", lambda s: s in stopped)
    monkeypatch.setattr(health, "clear_intent_marker", lambda s: None)
    monkeypatch.setattr(health, "heartbeat_age", lambda now=None: age)
    monkeypatch.setattr(health, "stale_threshold", lambda: threshold)
    monkeypatch.setattr(health, "seconds_since_wake", lambda now=None: since_wake)
    monkeypatch.setattr(health, "screen_recording_ok", lambda: sr_ok)
    monkeypatch.setattr(health, "base_dir_writable", lambda: writable)


def test_capture_health_all_ok(monkeypatch):
    _stub_health(monkeypatch, ups={"record": True, "serve": True, "watch": True}, age=5.0)
    h = health.capture_health()
    assert h.healthy is True
    assert h.problems == []


def test_capture_health_record_down(monkeypatch):
    _stub_health(monkeypatch, ups={"record": False, "serve": True, "watch": True}, age=5.0)
    h = health.capture_health()
    assert h.record_up is False
    assert any("record process is not running" in p for p in h.problems)


def test_capture_health_intentional_stop_is_silent(monkeypatch):
    _stub_health(monkeypatch, ups={"record": False, "serve": True, "watch": True},
                 age=5.0, stopped=("record",))
    h = health.capture_health()
    assert h.healthy is True


def test_capture_health_stale_heartbeat(monkeypatch):
    _stub_health(monkeypatch, ups={"record": True, "serve": True, "watch": True},
                 age=999.0, threshold=120.0, since_wake=9999.0)
    h = health.capture_health()
    assert h.heartbeat_stale is True
    assert any("heartbeat" in p for p in h.problems)


def test_capture_health_wake_grace_suppresses_stale(monkeypatch):
    _stub_health(monkeypatch, ups={"record": True, "serve": True, "watch": True},
                 age=999.0, threshold=120.0, since_wake=10.0)  # just woke
    h = health.capture_health()
    assert h.heartbeat_stale is True
    assert not any("heartbeat" in p for p in h.problems)  # suppressed


def test_capture_health_permission_and_disk(monkeypatch):
    _stub_health(monkeypatch, ups={"record": True, "serve": True, "watch": True},
                 age=5.0, sr_ok=False, writable=False)
    h = health.capture_health()
    assert any("permission" in p for p in h.problems)
    assert any("writable" in p or "disk" in p for p in h.problems)


def test_capture_health_running_record_without_heartbeat_is_stale(monkeypatch):
    # record is up but no heartbeat file exists yet (age None) -> treated as stale and flagged.
    _stub_health(monkeypatch, ups={"record": True, "serve": True, "watch": True},
                 age=None, threshold=120.0, since_wake=9999.0)
    h = health.capture_health()
    assert h.heartbeat_stale is True
    assert any("heartbeat" in p for p in h.problems)
