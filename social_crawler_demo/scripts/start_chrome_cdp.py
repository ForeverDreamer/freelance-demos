"""跨平台启动 Chrome 实例 w/ --remote-debugging-port 供 scrapy-playwright attach。

每平台独立 user-data-dir + 独立端口，cookie/登录态互不污染。
启动后需手动登录目标平台；session 持久化到 user-data-dir，下次免登录。

用法:
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
    """按平台依次探测 Chrome 可执行路径。环境变量 CHROME_PATH 优先级最高。"""
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
        help="目标平台 (决定默认端口 + user-data-dir)",
    )
    parser.add_argument("--port", type=int, default=None, help="CDP 端口（默认按 platform 选）")
    parser.add_argument("--user-data-dir", type=str, default=None, help="Chrome user data dir")
    parser.add_argument("--chrome-path", type=str, default=None, help="显式 Chrome 可执行路径")
    parser.add_argument(
        "--no-maximize", action="store_true", help="不使用 --start-maximized"
    )
    args = parser.parse_args()

    # 解析端口
    env_port = os.getenv(f"{args.platform.upper()}_CDP_PORT")
    port = args.port or (int(env_port) if env_port else PLATFORM_DEFAULT_PORTS[args.platform])

    # 解析 user-data-dir
    user_data_dir = Path(args.user_data_dir) if args.user_data_dir else default_user_data_dir(args.platform)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # 解析 Chrome path
    chrome_path = args.chrome_path or detect_chrome_path()
    if not chrome_path:
        logger.error(
            "未能检测到 Chrome 可执行路径。请设置 CHROME_PATH 环境变量或 --chrome-path 参数。\n"
            "当前系统: %s；检查过的路径: %s",
            platform.system(),
            CHROME_CANDIDATES.get(platform.system(), []),
        )
        return 1

    # 探测端口
    if not is_port_available(port):
        logger.error(
            "端口 %d 已被占用。可能已有 Chrome CDP 实例在跑；"
            "若要重启请先关闭对应 Chrome 窗口。",
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
    logger.info("启动 Chrome... (Ctrl+C 退出)")
    logger.info("=" * 60)
    logger.info("请在打开的 Chrome 窗口中登录目标平台（首次需要），session 会持久化。")
    logger.info("=" * 60)

    try:
        process = subprocess.Popen(cmd)
        process.wait()
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，终止 Chrome 进程")
        process.terminate()
        process.wait(timeout=5)
    except Exception as exc:
        logger.error("启动失败: %s", exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
