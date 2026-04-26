"""LLM provider registry. Six providers across three structured-output modes:
openai_strict (token-level schema enforcement), json_object (JSON mode + schema in
prompt + Pydantic validation), anthropic_tool (tool_use with input_schema)."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class StructuredOutputMode(str, Enum):
    OPENAI_STRICT = "openai_strict"
    JSON_OBJECT = "json_object"
    ANTHROPIC_TOOL = "anthropic_tool"


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key_env: str
    base_url: str | None
    default_model: str
    mode: StructuredOutputMode


PROVIDERS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="openai",
        api_key_env="OPENAI_API_KEY",
        base_url=None,
        default_model="gpt-4o-2024-08-06",
        mode=StructuredOutputMode.OPENAI_STRICT,
    ),
    "deepseek": ProviderConfig(
        name="deepseek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        mode=StructuredOutputMode.JSON_OBJECT,
    ),
    "kimi": ProviderConfig(
        name="kimi",
        api_key_env="MOONSHOT_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-32k",
        mode=StructuredOutputMode.JSON_OBJECT,
    ),
    "minimax": ProviderConfig(
        name="minimax",
        api_key_env="MINIMAX_API_KEY",
        base_url="https://api.minimax.chat/v1",
        default_model="abab6.5s-chat",
        mode=StructuredOutputMode.JSON_OBJECT,
    ),
    "gemini": ProviderConfig(
        name="gemini",
        api_key_env="GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        default_model="gemini-2.0-flash",
        mode=StructuredOutputMode.JSON_OBJECT,
    ),
    "claude": ProviderConfig(
        name="claude",
        api_key_env="ANTHROPIC_API_KEY",
        base_url=None,
        default_model="claude-sonnet-4-5",
        mode=StructuredOutputMode.ANTHROPIC_TOOL,
    ),
}


def resolve(name: str) -> ProviderConfig:
    key = name.lower()
    if key not in PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER: {name!r}. Expected one of: "
            f"{sorted(PROVIDERS)}"
        )
    return PROVIDERS[key]
