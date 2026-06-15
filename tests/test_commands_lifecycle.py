import memos.commands as commands


def test_stop_all_on_macos_marks_and_kills(monkeypatch):
    monkeypatch.setattr(commands, "is_macos", lambda: True)
    marked, stopped = [], []
    monkeypatch.setattr("memos.service_manager.mark_service_stopped", lambda s: marked.append(s))
    import memos.launchd as launchd
    monkeypatch.setattr(launchd, "stop", lambda s: stopped.append(s))
    commands.stop("all")
    assert set(marked) == {"record", "serve", "watch"}
    assert set(stopped) == {"record", "serve", "watch"}


def test_stop_single_on_macos(monkeypatch):
    monkeypatch.setattr(commands, "is_macos", lambda: True)
    marked, stopped = [], []
    monkeypatch.setattr("memos.service_manager.mark_service_stopped", lambda s: marked.append(s))
    import memos.launchd as launchd
    monkeypatch.setattr(launchd, "stop", lambda s: stopped.append(s))
    commands.stop("record")
    assert marked == ["record"]
    assert stopped == ["record"]


def test_start_on_macos_clears_marker_and_kickstarts(monkeypatch):
    monkeypatch.setattr(commands, "is_macos", lambda: True)
    cleared, started = [], []
    monkeypatch.setattr("memos.service_manager.clear_intent_marker", lambda s: cleared.append(s))
    import memos.launchd as launchd
    monkeypatch.setattr(launchd, "start", lambda s: started.append(s))
    commands.start("record")
    assert cleared == ["record"]
    assert started == ["record"]


def test_enable_on_macos_calls_launchd(monkeypatch):
    monkeypatch.setattr(commands, "is_macos", lambda: True)
    monkeypatch.setattr(commands, "is_windows", lambda: False)
    called = {"enable": False}
    import memos.launchd as launchd
    monkeypatch.setattr(launchd, "enable", lambda: called.__setitem__("enable", True))
    commands.enable()
    assert called["enable"] is True
