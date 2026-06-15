import memos.service_manager as sm


def test_intent_marker_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "get_pid_dir", lambda: tmp_path)
    assert sm.is_intentionally_stopped("record") is False
    sm.mark_service_stopped("record")
    assert sm.is_intentionally_stopped("record") is True
    assert (tmp_path / "record.stopped").exists()
    sm.clear_intent_marker("record")
    assert sm.is_intentionally_stopped("record") is False


def test_clear_intent_marker_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "get_pid_dir", lambda: tmp_path)
    # Clearing a marker that was never set must not raise.
    sm.clear_intent_marker("watch")
