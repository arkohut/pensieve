"""macOS launchd management: per-service KeepAlive agents + a periodic healthcheck.

Replaces the single `launch.sh` wrapper agent (which masked individual service
deaths) with four independent LaunchAgents so launchd supervises each process and
restarts it on crash. Lifecycle commands drive launchctl so launchd is the sole
process owner.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from memos.config import settings

SERVICE_LABELS = {
    "record": "com.user.memos.record",
    "serve": "com.user.memos.serve",
    "watch": "com.user.memos.watch",
}
HEALTHCHECK_LABEL = "com.user.memos.healthcheck"
LEGACY_LABEL = "com.user.memos"


def _domain() -> str:
    return f"gui/{os.getuid()}"


def plist_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def service_plist_path(service: str) -> Path:
    return plist_dir() / f"{SERVICE_LABELS[service]}.plist"


def healthcheck_plist_path() -> Path:
    return plist_dir() / f"{HEALTHCHECK_LABEL}.plist"


def legacy_plist_path() -> Path:
    return plist_dir() / f"{LEGACY_LABEL}.plist"


def env_path(python_dir: str) -> str:
    return f"{python_dir}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def build_service_plist(service: str, python_path: str, log_dir: Path, env_path: str) -> str:
    label = SERVICE_LABELS[service]
    py = escape(python_path)
    log_path = escape(str(log_dir / f"{service}.log"))
    path_env = escape(env_path)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py}</string>
        <string>-m</string>
        <string>memos.commands</string>
        <string>{service}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{path_env}</string>
    </dict>
</dict>
</plist>
"""


def build_healthcheck_plist(python_path: str, log_dir: Path, env_path: str, interval: int) -> str:
    py = escape(python_path)
    log_path = escape(str(log_dir / "healthcheck.log"))
    path_env = escape(env_path)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{HEALTHCHECK_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py}</string>
        <string>-m</string>
        <string>memos.commands</string>
        <string>health-check</string>
        <string>--notify</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>{interval}</integer>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{path_env}</string>
    </dict>
</dict>
</plist>
"""


def bootstrap_argv(plist_path) -> list:
    return ["launchctl", "bootstrap", _domain(), str(plist_path)]


def bootout_argv(label: str) -> list:
    return ["launchctl", "bootout", f"{_domain()}/{label}"]


def kickstart_argv(label: str, kill: bool = False) -> list:
    cmd = ["launchctl", "kickstart"]
    if kill:
        cmd.append("-k")
    cmd.append(f"{_domain()}/{label}")
    return cmd


def kill_argv(signal_name: str, label: str) -> list:
    return ["launchctl", "kill", signal_name, f"{_domain()}/{label}"]


def get_python_path() -> str:
    return sys.executable


def _run(argv: list) -> None:
    """Run a launchctl command, tolerating non-zero exit (e.g. not-loaded)."""
    try:
        result = subprocess.run(argv, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            logging.debug(
                "launchctl %s exited %s: %s", argv, result.returncode, (result.stderr or "").strip()
            )
    except Exception as e:
        logging.warning("launchctl command failed (%s): %s", argv, e)


def write_plists() -> list:
    """Write all four agent plists and return their paths."""
    pdir = plist_dir()
    pdir.mkdir(parents=True, exist_ok=True)
    log_dir = settings.resolved_base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    python_path = get_python_path()
    python_dir = os.path.dirname(python_path)
    path_env = env_path(python_dir)

    paths = []
    for service in SERVICE_LABELS:
        p = service_plist_path(service)
        p.write_text(build_service_plist(service, python_path, log_dir, path_env))
        paths.append(p)

    hc = healthcheck_plist_path()
    hc.write_text(build_healthcheck_plist(python_path, log_dir, path_env, settings.health.check_interval))
    paths.append(hc)
    return paths


def _migrate_legacy() -> None:
    """Tear down the old single-agent setup so launchd owns fresh per-service copies."""
    from .service_manager import stop_service

    _run(bootout_argv(LEGACY_LABEL))            # stop old wrapper job (kills its children)
    for svc in ("watch", "record", "serve"):    # belt-and-suspenders: free any PID-file locks
        stop_service(svc)

    legacy = legacy_plist_path()
    if legacy.exists():
        legacy.unlink()
    launch_sh = settings.resolved_base_dir / "launch.sh"
    if launch_sh.exists():
        launch_sh.unlink()


def enable() -> None:
    _migrate_legacy()
    for p in write_plists():
        _run(bootstrap_argv(p))


def disable() -> None:
    for label in (*SERVICE_LABELS.values(), HEALTHCHECK_LABEL, LEGACY_LABEL):
        _run(bootout_argv(label))
    for p in (
        *[service_plist_path(s) for s in SERVICE_LABELS],
        healthcheck_plist_path(),
        legacy_plist_path(),
    ):
        if p.exists():
            p.unlink()


def start(service: str) -> None:
    # No -k: start if down, no-op if already running (idempotent).
    _run(kickstart_argv(SERVICE_LABELS[service]))


def stop(service: str) -> None:
    _run(kill_argv("SIGTERM", SERVICE_LABELS[service]))


def restart(service: str) -> None:
    # -k: kill and restart even if currently running.
    _run(kickstart_argv(SERVICE_LABELS[service], kill=True))
