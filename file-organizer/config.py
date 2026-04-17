"""Rules loader for the file organizer.

Supports YAML (primary, via pyyaml) and JSON (fallback, stdlib). Normalizes
extensions to lowercase without the leading dot.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import yaml


@dataclass
class Action:
    type: str
    target: str


@dataclass
class Rule:
    name: str
    extensions: list[str] = field(default_factory=list)
    action: Optional[Action] = None


@dataclass
class Config:
    rules: list[Rule]


def load_config(path: Union[str, Path]) -> Config:
    """Load rules from a YAML or JSON file.

    Raises ValueError for unsupported file extensions.
    """
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    suffix = p.suffix.lower()
    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    elif suffix == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(
            f"Unsupported config format: {p.suffix}. Use .yaml, .yml, or .json."
        )

    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping with a 'rules' key.")

    rules: list[Rule] = []
    for rule_data in data.get("rules", []):
        extensions = [
            e.lower().lstrip(".")
            for e in rule_data.get("match", {}).get("extensions", [])
        ]
        action_data = rule_data.get("action")
        action = None
        if action_data:
            action = Action(type=action_data["type"], target=action_data["target"])
        rules.append(
            Rule(name=rule_data["name"], extensions=extensions, action=action)
        )

    return Config(rules=rules)


def match_rule(config: Config, filename: Union[str, Path]) -> Optional[Rule]:
    """Return the first rule whose extension set contains filename's extension.

    Returns None when no rule matches. Matching is case-insensitive.
    """
    ext = Path(filename).suffix.lower().lstrip(".")
    for rule in config.rules:
        if ext in rule.extensions:
            return rule
    return None
