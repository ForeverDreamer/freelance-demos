"""Tests for config.py: YAML / JSON loading and rule matching."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from config import load_config, match_rule


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_load_yaml(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "rules.yaml",
        """
rules:
  - name: images
    match:
      extensions: [jpg, png]
    action:
      type: move
      target: ./routed/images
""",
    )
    config = load_config(path)
    assert len(config.rules) == 1
    assert config.rules[0].name == "images"
    assert config.rules[0].extensions == ["jpg", "png"]
    assert config.rules[0].action is not None
    assert config.rules[0].action.type == "move"
    assert config.rules[0].action.target == "./routed/images"


def test_load_json(tmp_path: Path) -> None:
    payload = {
        "rules": [
            {
                "name": "docs",
                "match": {"extensions": [".PDF", "DOCX"]},
                "action": {"type": "move", "target": "./routed/docs"},
            }
        ]
    }
    path = _write(tmp_path / "rules.json", json.dumps(payload))
    config = load_config(path)
    # Extensions normalized: lowercase, no leading dot
    assert config.rules[0].extensions == ["pdf", "docx"]


def test_unsupported_format(tmp_path: Path) -> None:
    path = _write(tmp_path / "rules.toml", "foo = 1")
    with pytest.raises(ValueError, match="Unsupported config format"):
        load_config(path)


def test_match_case_insensitive(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "rules.yaml",
        """
rules:
  - name: images
    match:
      extensions: [jpg, png]
    action:
      type: move
      target: ./out
""",
    )
    config = load_config(path)
    assert match_rule(config, "foo.jpg").name == "images"
    assert match_rule(config, "foo.JPG").name == "images"
    assert match_rule(config, "bar.txt") is None


def test_first_rule_wins(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "rules.yaml",
        """
rules:
  - name: first
    match:
      extensions: [log]
    action:
      type: move
      target: ./first
  - name: second
    match:
      extensions: [log]
    action:
      type: move
      target: ./second
""",
    )
    config = load_config(path)
    assert match_rule(config, "x.log").name == "first"
