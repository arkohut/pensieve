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
