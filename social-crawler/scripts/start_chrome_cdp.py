"""Cross-platform Chrome launcher with --remote-debugging-port for CDP attach.

Each platform runs in its own user-data-dir so cookies do not cross-contaminate.
After the Chrome window opens, the user logs in manually if needed; the
session persists in the user-data-dir and is reused on subsequent runs.

Public demo scope: 2 platforms (twitter / tiktok). The paid version adds
Facebook / Instagram launchers plus a residential-proxy binding mode.

⚠️ Chrome 136+ security note
    Since 2025-03 Chrome silently ignores --remote-debugging-port if the
    user-data-dir is the OS default (anti cookie-theft). This script defaults
    to ~/.chrome-profiles/<platform>/, which is non-default — so the default
    invocation is unaffected. **Do not** point CHROME_USER_DATA_BASE at the
    Chrome default path:
        Win:   %LOCALAPPDATA%\\Google\\Chrome\\User Data
        macOS: ~/Library/Application Support/Google/Chrome
        Linux: ~/.config/google-chrome

Usage:
    python scripts/start_chrome_cdp.py --platform twitter
    python scripts/start_chrome_cdp.py --platform tiktok --port 9225
"""
from __future__ import annotations

import argparse
import logging
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PLATFORM_DEFAULT_PORTS = {
    "twitter": 9223,
    "tiktok": 9225,
}

CHROME_CANDIDATES = {
    "Darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ],
    "Linux": [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        # WSL2 → Windows Chrome
        "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
        "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ],
    "Windows": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
}


def detect_chrome_path() -> str | None:
    """Probe candidate Chrome paths per OS. CHROME_PATH env var has highest priority."""
    env = os.getenv("CHROME_PATH")
    if env and Path(env).exists():
        return env

    system = platform.system()
    for candidate in CHROME_CANDIDATES.get(system, []):
        if Path(candidate).exists():
            return candidate
    return None


def is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def default_user_data_dir(platform_name: str) -> Path:
    base = os.getenv("CHROME_USER_DATA_BASE")
    if base:
        return Path(base) / platform_name
    return Path.home() / ".chrome-profiles" / platform_name


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--platform",
        required=True,
        choices=list(PLATFORM_DEFAULT_PORTS.keys()),
        help="Target platform (sets default port + user-data-dir)",
    )
    parser.add_argument("--port", type=int, default=None, help="CDP port (default per-platform)")
    parser.add_argument("--user-data-dir", type=str, default=None, help="Chrome user data dir")
    parser.add_argument("--chrome-path", type=str, default=None, help="Explicit Chrome path")
    parser.add_argument("--no-maximize", action="store_true", help="Skip --start-maximized")
    args = parser.parse_args()

    env_port = os.getenv(f"{args.platform.upper()}_CDP_PORT")
    port = args.port or (int(env_port) if env_port else PLATFORM_DEFAULT_PORTS[args.platform])

    user_data_dir = (
        Path(args.user_data_dir) if args.user_data_dir else default_user_data_dir(args.platform)
    )
    user_data_dir.mkdir(parents=True, exist_ok=True)

    chrome_path = args.chrome_path or detect_chrome_path()
    if not chrome_path:
        logger.error(
            "Could not locate Chrome. Set CHROME_PATH env var or pass --chrome-path.\n"
            "OS: %s, candidates checked: %s",
            platform.system(),
            CHROME_CANDIDATES.get(platform.system(), []),
        )
        return 1

    if not is_port_available(port):
        logger.error(
            "Port %d already in use. Likely an existing Chrome CDP instance is "
            "running; close that Chrome window first to restart on the same port.",
            port,
        )
        return 2

    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if not args.no_maximize:
        cmd.append("--start-maximized")

    # Deliberately do NOT pass an initial URL on the command line. A URL passed
    # via argv is a programmatic navigation — anti-bot detectors flag the
    # `sec-fetch-user=?0` it produces. Open the platform homepage manually
    # via Ctrl+T + address bar after Chrome starts.

    logger.info("Platform: %s", args.platform)
    logger.info("Chrome: %s", chrome_path)
    logger.info("Port: %d", port)
    logger.info("User data dir: %s", user_data_dir)
    logger.info("Launching Chrome... (Ctrl+C to stop)")
    logger.info("=" * 60)
    logger.info("After the window opens: Ctrl+T → type the platform homepage URL → Enter.")
    logger.info("Log in manually if the platform requires it. Session persists.")
    logger.info("=" * 60)

    try:
        process = subprocess.Popen(cmd)
        process.wait()
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C; terminating Chrome process")
        process.terminate()
        process.wait(timeout=5)
    except Exception as exc:
        logger.error("Launch failed: %s", exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
