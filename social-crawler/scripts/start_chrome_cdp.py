"""Cross-platform Chrome launcher with --remote-debugging-port for scrapy-playwright attach.

Each platform gets its own user-data-dir and CDP port so cookies and login state stay isolated.
Log in manually after Chrome opens; the session persists in user-data-dir for later runs.

Usage:
    python scripts/start_chrome_cdp.py --platform fb
    python scripts/start_chrome_cdp.py --platform twitter --port 9223
    python scripts/start_chrome_cdp.py --platform instagram --user-data-dir /tmp/ig
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
    "fb": 9222,
    "twitter": 9223,
    "instagram": 9224,
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
    """Probe for a Chrome executable per OS. CHROME_PATH environment variable takes precedence."""
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

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--platform",
        required=True,
        choices=list(PLATFORM_DEFAULT_PORTS.keys()),
        help="Target platform (selects default port and user-data-dir)",
    )
    parser.add_argument("--port", type=int, default=None, help="CDP port (defaults are per-platform)")
    parser.add_argument("--user-data-dir", type=str, default=None, help="Chrome user data dir")
    parser.add_argument("--chrome-path", type=str, default=None, help="Explicit path to a Chrome executable")
    parser.add_argument(
        "--no-maximize", action="store_true", help="Do not pass --start-maximized to Chrome"
    )
    args = parser.parse_args()

    # Resolve port
    env_port = os.getenv(f"{args.platform.upper()}_CDP_PORT")
    port = args.port or (int(env_port) if env_port else PLATFORM_DEFAULT_PORTS[args.platform])

    # Resolve user-data-dir
    user_data_dir = Path(args.user_data_dir) if args.user_data_dir else default_user_data_dir(args.platform)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # Resolve Chrome path
    chrome_path = args.chrome_path or detect_chrome_path()
    if not chrome_path:
        logger.error(
            "Could not detect a Chrome executable. Set the CHROME_PATH environment variable or pass --chrome-path.\n"
            "Current OS: %s; paths checked: %s",
            platform.system(),
            CHROME_CANDIDATES.get(platform.system(), []),
        )
        return 1

    # Probe port
    if not is_port_available(port):
        logger.error(
            "Port %d is already in use. A Chrome CDP instance may already be running; "
            "close that Chrome window first if you want to restart.",
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

    logger.info("Platform: %s", args.platform)
    logger.info("Chrome: %s", chrome_path)
    logger.info("Port: %d", port)
    logger.info("User data dir: %s", user_data_dir)
    logger.info("Launching Chrome... (Ctrl+C to exit)")
    logger.info("=" * 60)
    logger.info("Log in to the target platform in the Chrome window if needed; the session will persist.")
    logger.info("=" * 60)

    try:
        process = subprocess.Popen(cmd)
        process.wait()
    except KeyboardInterrupt:
        logger.info("Ctrl+C received, terminating Chrome process")
        process.terminate()
        process.wait(timeout=5)
    except Exception as exc:
        logger.error("Launch failed: %s", exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
