"""Latency measurement.

The headline demo claim is 'detection under 2 seconds'. This test starts
an observer, drops a file, and measures the gap between creation and
handler invocation.
"""
from __future__ import annotations

import time
from pathlib import Path

from watchdog.observers import Observer

from config import Action, Config, Rule
from organizer import OrganizerHandler


def test_detection_under_2_seconds(tmp_path: Path) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    target_dir = tmp_path / "routed"

    config = Config(
        rules=[
            Rule(
                name="any-txt",
                extensions=["txt"],
                action=Action(type="move", target=str(target_dir)),
            )
        ]
    )

    detected_at: list[float] = []
    handler = OrganizerHandler(config)
    original = handler._process

    def wrapper(src_path: str) -> None:
        detected_at.append(time.monotonic())
        original(src_path)

    handler._process = wrapper  # type: ignore[method-assign]

    observer = Observer()
    observer.schedule(handler, str(watched), recursive=False)
    observer.start()

    # Give the observer a brief moment to install filesystem hooks
    time.sleep(0.1)

    try:
        dropped_at = time.monotonic()
        (watched / "probe.txt").write_text("hello")

        # Wait up to 2s for detection to fire
        deadline = dropped_at + 2.0
        while time.monotonic() < deadline and not detected_at:
            time.sleep(0.02)

        assert detected_at, "Detection did not fire within 2 seconds"
        latency = detected_at[0] - dropped_at
        assert latency < 2.0, f"Latency {latency:.3f}s exceeded 2s budget"
    finally:
        observer.stop()
        observer.join(timeout=2)
