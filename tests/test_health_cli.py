from typer.testing import CliRunner
import memos.commands as commands
import memos.health as health

runner = CliRunner()


def _fake_health(problems):
    return health.CaptureHealth(
        record_up=not problems, serve_up=True, watch_up=True,
        heartbeat_age=5.0, heartbeat_stale=False,
        screen_recording_ok=True, base_dir_writable=True, problems=problems,
    )


def test_health_check_ok_exits_zero(monkeypatch):
    monkeypatch.setattr("memos.health.capture_health", lambda: _fake_health([]))
    result = runner.invoke(commands.app, ["health-check"])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_health_check_problem_exits_nonzero(monkeypatch):
    monkeypatch.setattr("memos.health.capture_health", lambda: _fake_health(["record process is not running"]))
    result = runner.invoke(commands.app, ["health-check"])
    assert result.exit_code == 1
    assert "record process is not running" in result.stdout


def test_health_check_notify_calls_alert(monkeypatch):
    monkeypatch.setattr("memos.health.capture_health", lambda: _fake_health(["x"]))
    sent = {"n": 0}
    monkeypatch.setattr("memos.notify.alert_if_changed", lambda problems: sent.__setitem__("n", sent["n"] + 1))
    runner.invoke(commands.app, ["health-check", "--notify"])
    assert sent["n"] == 1


def test_doctor_shows_capture_health(monkeypatch):
    monkeypatch.setattr("memos.health.capture_health", lambda: _fake_health([]))
    # Keep doctor's own preflight from forcing a nonzero exit / prompts:
    monkeypatch.setattr(commands, "is_macos", lambda: False)
    monkeypatch.setattr(commands, "is_windows", lambda: False)
    result = runner.invoke(commands.app, ["doctor"])
    assert "Capture: record" in result.stdout
