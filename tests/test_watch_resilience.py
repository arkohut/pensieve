"""Regression tests for the watch service crashing on transient OS state.

Background: on 2026-06-03 the watch service died with
``TypeError: 'NoneType' object is not subscriptable`` because
``NSWorkspace.sharedWorkspace().activeApplication()`` returned ``None`` (which
happens momentarily on screen lock, app switching, or display wake) and the
darwin helper indexed into it directly. The watch main loop only guarded
``KeyboardInterrupt``, so the exception killed the process and nothing restarted
it.

These tests cover the fixes:
  1. ``get_active_window_info_darwin`` degrades to empty info instead of raising
     when either ``activeApplication()`` or ``CGWindowListCopyWindowInfo()``
     returns ``None`` (both happen on screen lock / display wake / app switch).
  2. The watch poll loop isolates each cycle so a failing cycle is logged and the
     watcher keeps running.
"""


def test_get_active_window_info_darwin_returns_default_when_no_active_app(monkeypatch):
    import memos.record as record

    class _FakeWorkspace:
        def activeApplication(self):
            return None

    class _FakeNSWorkspace:
        @staticmethod
        def sharedWorkspace():
            return _FakeWorkspace()

    monkeypatch.setattr(record, "NSWorkspace", _FakeNSWorkspace, raising=False)

    assert record.get_active_window_info_darwin() == ("", "", None)


def test_get_active_window_info_darwin_returns_app_only_when_no_window_list(monkeypatch):
    import memos.record as record

    class _FakeWorkspace:
        def activeApplication(self):
            return {
                "NSApplicationName": "TestApp",
                "NSApplicationProcessIdentifier": 4321,
            }

    class _FakeNSWorkspace:
        @staticmethod
        def sharedWorkspace():
            return _FakeWorkspace()

    monkeypatch.setattr(record, "NSWorkspace", _FakeNSWorkspace, raising=False)
    # CGWindowListCopyWindowInfo() returns None when the window list is
    # unavailable; the helper must not iterate over it.
    monkeypatch.setattr(
        record, "CGWindowListCopyWindowInfo", lambda *a, **k: None, raising=False
    )

    assert record.get_active_window_info_darwin() == ("TestApp", "", None)


def test_watch_poll_loop_survives_failing_cycle(monkeypatch):
    import memos.cmds.library as library

    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        raise TypeError("'NoneType' object is not subscriptable")

    monkeypatch.setattr(library, "get_active_window_info", boom)

    # A cycle that raises must not propagate out of the loop; it should run every
    # requested iteration. Without isolation this raises on the first cycle.
    library._watch_poll_loop([], iterations=3, sleep_fn=lambda _interval: None)

    assert calls["n"] == 3
