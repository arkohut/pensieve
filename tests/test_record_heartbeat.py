import memos.record as record


def test_run_screen_recorder_touches_heartbeat_each_iteration(monkeypatch, tmp_path):
    calls = {"n": 0}
    monkeypatch.setattr(record, "touch_heartbeat", lambda: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(record, "is_screen_locked", lambda: True)  # skip the capture path
    record.run_screen_recorder(
        4, str(tmp_path), {}, iterations=3, sleep_fn=lambda _interval: None
    )
    assert calls["n"] == 3


def test_run_screen_recorder_touches_heartbeat_even_on_cycle_error(monkeypatch, tmp_path):
    calls = {"n": 0}
    monkeypatch.setattr(record, "touch_heartbeat", lambda: calls.__setitem__("n", calls["n"] + 1))
    def boom():
        raise RuntimeError("transient")
    monkeypatch.setattr(record, "is_screen_locked", boom)  # body raises every cycle
    record.run_screen_recorder(
        4, str(tmp_path), {}, iterations=2, sleep_fn=lambda _interval: None
    )
    assert calls["n"] == 2  # heartbeat still advanced despite errors
