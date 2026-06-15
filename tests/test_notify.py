import memos.notify as notify


def test_notify_runs_osascript_on_darwin(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(notify.subprocess, "run", lambda argv, **k: calls.append(argv))
    notify.notify("Pensieve", "capture stopped")
    assert calls, "expected osascript to be invoked"
    argv = calls[0]
    assert argv[0] == "osascript"
    joined = " ".join(argv)
    assert "display notification" in joined
    assert "capture stopped" in joined
    assert "Pensieve" in joined


def test_notify_noop_off_darwin(monkeypatch):
    calls = []
    monkeypatch.setattr(notify.platform, "system", lambda: "Linux")
    monkeypatch.setattr(notify.subprocess, "run", lambda *a, **k: calls.append(a))
    notify.notify("Pensieve", "x")
    assert calls == []


def test_notify_never_raises(monkeypatch):
    monkeypatch.setattr(notify.platform, "system", lambda: "Darwin")
    def boom(*a, **k):
        raise OSError("no osascript")
    monkeypatch.setattr(notify.subprocess, "run", boom)
    notify.notify("Pensieve", "x")  # must not raise


def test_alert_fires_on_first_problem(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "notify", lambda t, m: sent.append((t, m)))
    state = tmp_path / "health.state"
    result = notify.alert_if_changed(["record process is not running"],
                                     now=1000.0, state_path=state, cooldown=3600)
    assert result == "problem"
    assert len(sent) == 1


def test_alert_suppressed_within_cooldown_same_problem(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "notify", lambda t, m: sent.append((t, m)))
    state = tmp_path / "health.state"
    notify.alert_if_changed(["x"], now=1000.0, state_path=state, cooldown=3600)
    result = notify.alert_if_changed(["x"], now=1500.0, state_path=state, cooldown=3600)
    assert result is None
    assert len(sent) == 1  # not re-sent


def test_alert_refires_after_cooldown(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "notify", lambda t, m: sent.append((t, m)))
    state = tmp_path / "health.state"
    notify.alert_if_changed(["x"], now=1000.0, state_path=state, cooldown=3600)
    result = notify.alert_if_changed(["x"], now=1000.0 + 3601, state_path=state, cooldown=3600)
    assert result == "problem"
    assert len(sent) == 2


def test_alert_fires_when_problem_set_changes(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "notify", lambda t, m: sent.append((t, m)))
    state = tmp_path / "health.state"
    notify.alert_if_changed(["x"], now=1000.0, state_path=state, cooldown=3600)
    result = notify.alert_if_changed(["x", "y"], now=1100.0, state_path=state, cooldown=3600)
    assert result == "problem"
    assert len(sent) == 2


def test_recovered_notification(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(notify, "notify", lambda t, m: sent.append((t, m)))
    state = tmp_path / "health.state"
    notify.alert_if_changed(["x"], now=1000.0, state_path=state, cooldown=3600)
    result = notify.alert_if_changed([], now=1100.0, state_path=state, cooldown=3600)
    assert result == "recovered"
    assert len(sent) == 2
    result2 = notify.alert_if_changed([], now=1200.0, state_path=state, cooldown=3600)
    assert result2 is None  # already healthy, no repeat
