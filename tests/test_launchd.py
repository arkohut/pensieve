import memos.launchd as launchd


def test_service_label_mapping():
    assert launchd.SERVICE_LABELS["record"] == "com.user.memos.record"
    assert launchd.HEALTHCHECK_LABEL == "com.user.memos.healthcheck"
    assert launchd.LEGACY_LABEL == "com.user.memos"


def test_argv_builders(monkeypatch):
    monkeypatch.setattr(launchd, "_domain", lambda: "gui/501")
    assert launchd.bootstrap_argv("/p/x.plist") == ["launchctl", "bootstrap", "gui/501", "/p/x.plist"]
    assert launchd.bootout_argv("com.user.memos.record") == ["launchctl", "bootout", "gui/501/com.user.memos.record"]
    assert launchd.kickstart_argv("com.user.memos.record") == ["launchctl", "kickstart", "gui/501/com.user.memos.record"]
    assert launchd.kickstart_argv("com.user.memos.record", kill=True) == ["launchctl", "kickstart", "-k", "gui/501/com.user.memos.record"]
    assert launchd.kill_argv("SIGTERM", "com.user.memos.record") == ["launchctl", "kill", "SIGTERM", "gui/501/com.user.memos.record"]


def test_build_service_plist_contains_keepalive(tmp_path):
    xml = launchd.build_service_plist(
        "record", python_path="/usr/bin/python3", log_dir=tmp_path, env_path="/usr/bin"
    )
    assert "<key>Label</key>" in xml and "com.user.memos.record" in xml
    assert "memos.commands" in xml and "<string>record</string>" in xml
    assert "<key>KeepAlive</key>" in xml
    assert "<key>SuccessfulExit</key>" in xml and "<false/>" in xml
    assert "<key>ThrottleInterval</key>" in xml and "<integer>10</integer>" in xml
    assert "<key>RunAtLoad</key>" in xml and "<true/>" in xml
    assert str(tmp_path / "record.log") in xml


def test_build_healthcheck_plist_has_interval_and_notify(tmp_path):
    xml = launchd.build_healthcheck_plist(
        python_path="/usr/bin/python3", log_dir=tmp_path, env_path="/usr/bin", interval=600
    )
    assert "com.user.memos.healthcheck" in xml
    assert "<string>health-check</string>" in xml
    assert "<string>--notify</string>" in xml
    assert "<key>StartInterval</key>" in xml and "<integer>600</integer>" in xml


def test_write_plists_creates_four_files(tmp_path, monkeypatch):
    monkeypatch.setattr(launchd, "plist_dir", lambda: tmp_path)
    monkeypatch.setattr(launchd, "get_python_path", lambda: "/usr/bin/python3", raising=False)
    paths = launchd.write_plists()
    names = sorted(p.name for p in paths)
    assert names == [
        "com.user.memos.healthcheck.plist",
        "com.user.memos.record.plist",
        "com.user.memos.serve.plist",
        "com.user.memos.watch.plist",
    ]
    for p in paths:
        assert p.exists()


def test_enable_migrates_then_bootstraps(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(launchd, "plist_dir", lambda: tmp_path)
    monkeypatch.setattr(launchd, "_run", lambda argv: ran.append(argv))
    monkeypatch.setattr(launchd, "_migrate_legacy", lambda: ran.append(["MIGRATED"]))
    launchd.enable()
    assert ["MIGRATED"] in ran
    bootstraps = [a for a in ran if a[:2] == ["launchctl", "bootstrap"]]
    assert len(bootstraps) == 4


def test_stop_kills_with_sigterm(monkeypatch):
    ran = []
    monkeypatch.setattr(launchd, "_run", lambda argv: ran.append(argv))
    monkeypatch.setattr(launchd, "_domain", lambda: "gui/501")
    launchd.stop("record")
    assert ran == [["launchctl", "kill", "SIGTERM", "gui/501/com.user.memos.record"]]


def test_start_kickstarts(monkeypatch):
    ran = []
    monkeypatch.setattr(launchd, "_run", lambda argv: ran.append(argv))
    monkeypatch.setattr(launchd, "_domain", lambda: "gui/501")
    launchd.start("record")
    assert ran == [["launchctl", "kickstart", "gui/501/com.user.memos.record"]]


def test_disable_boots_out_all_and_removes(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(launchd, "plist_dir", lambda: tmp_path)
    monkeypatch.setattr(launchd, "_run", lambda argv: ran.append(argv))
    # create a plist file so disable removes it
    (tmp_path / "com.user.memos.record.plist").write_text("x")
    launchd.disable()
    booted = [a[-1] for a in ran if a[:2] == ["launchctl", "bootout"]]
    assert any("com.user.memos.record" in b for b in booted)
    assert any("com.user.memos.healthcheck" in b for b in booted)
    assert not (tmp_path / "com.user.memos.record.plist").exists()


def test_restart_kickstarts(monkeypatch):
    ran = []
    monkeypatch.setattr(launchd, "_run", lambda argv: ran.append(argv))
    monkeypatch.setattr(launchd, "_domain", lambda: "gui/501")
    launchd.restart("record")
    assert ran == [["launchctl", "kickstart", "-k", "gui/501/com.user.memos.record"]]


def test_build_service_plist_escapes_xml_special_chars(tmp_path):
    from pathlib import Path
    xml = launchd.build_service_plist(
        "record", python_path="/usr/bin/py&thon", log_dir=Path("/tmp/a&b"), env_path="/x&y"
    )
    assert "&amp;" in xml
    assert "/usr/bin/py&thon" not in xml  # raw ampersand must not appear unescaped


def test_migrate_legacy_boots_out_stops_and_removes_files(tmp_path, monkeypatch):
    from types import SimpleNamespace
    ran = []
    stopped = []
    monkeypatch.setattr(launchd, "plist_dir", lambda: tmp_path)
    monkeypatch.setattr(launchd, "_run", lambda argv: ran.append(argv))
    monkeypatch.setattr(launchd, "_domain", lambda: "gui/501")
    monkeypatch.setattr(launchd, "settings", SimpleNamespace(resolved_base_dir=tmp_path))
    import memos.service_manager as sm
    monkeypatch.setattr(sm, "stop_service", lambda svc: stopped.append(svc))

    legacy = tmp_path / "com.user.memos.plist"
    legacy.write_text("x")
    launch_sh = tmp_path / "launch.sh"
    launch_sh.write_text("#!/bin/bash")

    launchd._migrate_legacy()

    assert ["launchctl", "bootout", "gui/501/com.user.memos"] in ran
    assert set(stopped) == {"record", "serve", "watch"}
    assert not legacy.exists()
    assert not launch_sh.exists()
