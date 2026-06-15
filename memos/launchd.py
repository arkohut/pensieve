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
from pathlib import Path

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
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
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
    <string>{log_dir / f"{service}.log"}</string>
    <key>StandardErrorPath</key>
    <string>{log_dir / f"{service}.log"}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{env_path}</string>
    </dict>
</dict>
</plist>
"""


def build_healthcheck_plist(python_path: str, log_dir: Path, env_path: str, interval: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{HEALTHCHECK_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
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
    <string>{log_dir / "healthcheck.log"}</string>
    <key>StandardErrorPath</key>
    <string>{log_dir / "healthcheck.log"}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{env_path}</string>
    </dict>
</dict>
</plist>
"""


def bootstrap_argv(plist_path) -> list:
    return ["launchctl", "bootstrap", _domain(), str(plist_path)]


def bootout_argv(label: str) -> list:
    return ["launchctl", "bootout", f"{_domain()}/{label}"]


def kickstart_argv(label: str) -> list:
    return ["launchctl", "kickstart", "-k", f"{_domain()}/{label}"]


def kill_argv(signal_name: str, label: str) -> list:
    return ["launchctl", "kill", signal_name, f"{_domain()}/{label}"]
