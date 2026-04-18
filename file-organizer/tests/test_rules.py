"""Tests for action application and error recovery."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import pytest

from actions.move import move
from config import Action, Config, Rule
from organizer import OrganizerHandler, _wait_until_stable


def test_move(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello")
    target_dir = tmp_path / "destination"

    destination = move(source, target_dir)

    assert destination.exists()
    assert destination.read_text() == "hello"
    assert not source.exists()
    assert destination.parent == target_dir


def test_move_collision(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("first")
    target_dir = tmp_path / "dst"
    target_dir.mkdir()
    (target_dir / "a.txt").write_text("existing")

    destination = move(source, target_dir)

    # Collision resolved with numeric suffix
    assert destination.name == "a-1.txt"
    assert destination.read_text() == "first"
    # Original untouched target is preserved
    assert (target_dir / "a.txt").read_text() == "existing"


def test_match_and_route(tmp_path: Path) -> None:
    """End-to-end: handler matches a rule and routes the file."""
    source = tmp_path / "photo.jpg"
    source.write_text("binary-ish")
    target_dir = tmp_path / "routed" / "images"

    config = Config(
        rules=[
            Rule(
                name="images",
                extensions=["jpg"],
                action=Action(type="move", target=str(target_dir)),
            )
        ]
    )
    handler = OrganizerHandler(config)
    handler._process(str(source))

    assert (target_dir / "photo.jpg").exists()
    assert not source.exists()


def test_no_rule_match_does_nothing(tmp_path: Path) -> None:
    source = tmp_path / "x.unknown"
    source.write_text("y")
    config = Config(rules=[])
    handler = OrganizerHandler(config)

    handler._process(str(source))

    # File untouched
    assert source.exists()


def test_wait_until_stable_waits_for_writer_to_finish(tmp_path: Path) -> None:
    """Simulate the Windows race: a process keeps writing while the watcher
    reacts. _wait_until_stable must hold off until the writes settle."""
    path = tmp_path / "growing.bin"
    path.write_bytes(b"")
    stop = threading.Event()

    def writer() -> None:
        while not stop.is_set():
            with open(path, "ab") as handle:
                handle.write(b"x")
            time.sleep(0.05)

    t = threading.Thread(target=writer, daemon=True)
    t.start()
    threading.Timer(0.3, stop.set).start()

    try:
        assert _wait_until_stable(str(path), timeout=2.0, interval=0.1) is True
        size_after = path.stat().st_size
        time.sleep(0.15)
        # File must not have grown after the helper returned stable.
        assert path.stat().st_size == size_after
    finally:
        stop.set()
        t.join(timeout=1)


def test_wait_until_stable_times_out_on_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    assert _wait_until_stable(str(missing), timeout=0.3, interval=0.05) is False


def test_error_recovery(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """When the action fails, the handler must log and return, not raise."""
    source = tmp_path / "x.txt"
    source.write_text("content")

    # Create a regular file at a path that the action will try to use as a
    # parent directory. mkdir(parents=True) will fail because an intermediate
    # path component is a file, not a directory.
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file")
    invalid_target = blocker / "subdir"

    config = Config(
        rules=[
            Rule(
                name="txt",
                extensions=["txt"],
                action=Action(type="move", target=str(invalid_target)),
            )
        ]
    )
    handler = OrganizerHandler(config)

    with caplog.at_level(logging.ERROR, logger="file-organizer"):
        handler._process(str(source))  # Must not raise

    # Error was logged
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert error_records, "Expected an ERROR log record from failed action"
    # Source file should still exist because move did not complete
    assert source.exists()
