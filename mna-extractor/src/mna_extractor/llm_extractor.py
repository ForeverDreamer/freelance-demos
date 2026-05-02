"""LLM extraction wrapper: DeepSeek primary, OpenAI / Anthropic fallback.

TODO during 实测 Module 2 (case.md §5.2 #2):
- Iterate prompt in docs/prompt_design.md, freeze v1.0 after 10-firm seed run hits target accuracy
- Compare extraction quality: deepseek-chat (cheapest at 10K scale, OpenAI-compatible)
  vs gpt-4o-mini vs claude-haiku-4-5 (better at structured extraction?)
- Implement Batch API mode for full 10K run (Module 4); pilot mode uses sync API for fast iteration
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .schema import FirmRecord


SYSTEM_PROMPT = """You are an extraction assistant that reads a private equity / M&A buyer firm's website HTML
and produces a structured JSON record matching the 33-column Buyer Database schema.

OUTPUT JSON FIELDS — use these EXACT field names, do NOT invent synonyms:

[FIRM IDENTITY]
- firm_name (str): canonical firm name
- firm_type (str): one of "Private Equity" | "Search Fund" | "Family Office" | "Strategic" | "SBIC" | "Growth Equity" | "HoldCo" | "Independent Sponsor" | "Unknown"
- website (URL str): provided URL, return as-is
- hq_location (str | null): "City, State/Province | Country" format, e.g. "New York, NY". Look for it in: footer copyright (e.g. "© 2024 Firm Inc., New York, NY"), CONTACT page office addresses (the FIRST listed or "Headquarters" / "HQ" / "Main Office" labeled one), ABOUT page "founded in X" / "based in X" sentences. If multiple offices listed, pick the one labeled HQ or the first/largest. If only city is clear, still emit it.
- key_contacts (list of {name, title, email?}): only if name+title explicitly on Team/Contact/About; do NOT invent

[INVESTMENT OVERVIEW]
- investment_capital_aum, ev_min_m, ev_max_m: ALWAYS emit literal "[REQUIRES EXTERNAL]" string (PE-internal numerical, not on website)
- revenue_model_preference (str | null): website-inferable, e.g. "Recurring revenue preferred" / "Project-based" / "Mixed" / null
- preferred_ebitda_margin_min, hold_period_strategy: ALWAYS emit literal "[REQUIRES EXTERNAL]"

[PLATFORM SEARCH CRITERIA]
- platform_industries (list[str]): firm's primary target industries for platform investments. Free-text; will be normalized later. THIS IS THE KEY FIELD — extract from PORTFOLIO/INVESTMENTS/ABOUT pages aggressively
- platform_geographies (list[str]): regions where firm invests, e.g. ["North America", "Europe"]
- platform_ebitda_min_k, platform_ebitda_max_m, platform_revenue_min_m, platform_revenue_max_m: ALWAYS "[REQUIRES EXTERNAL]"
- platform_additional_criteria (str | null): free-text platform criteria from website (e.g. "recession-resistant", "subscription-based")

[ADD-ON SEARCH CRITERIA]
- addon_industries (list[str]): typically a subset of platform_industries; often empty or same as platform
- addon_geographies (list[str]): typically same as platform_geographies; often empty
- addon_ebitda_min_k, addon_ebitda_max_m, addon_revenue_min_m, addon_revenue_max_m: ALWAYS "[REQUIRES EXTERNAL]"
- addon_opportunistic (str | null): null unless website says otherwise (e.g. "Yes — opportunistic add-ons across industries")
- addon_additional_criteria (str | null): free-text add-on criteria

[DEAL STRUCTURE]
- transaction_types (list[str]): e.g. ["Buyout", "Growth Equity", "Carve-out", "Recap", "Take-Private", "Founder Recap"]. Extract from "What we do" / "Investment criteria" sections
- min_ownership_pct, typical_debt_leverage: ALWAYS "[REQUIRES EXTERNAL]"

[META]
- source_urls (list[URL str]): leave EMPTY []; pipeline populates after extraction
- date_researched (str | null): null unless website provides
- confidence_level (str): "High" | "Medium" | "Low"
- notes (str | null): salient observations, asset class diversity, sector specialization, founding year, fund vintages

CRITICAL FIELD-NAME RULES:
- Headquarters → hq_location (NOT "headquarters", "location", "address")
- Primary industries / sectors → platform_industries (NOT "industries", "industries_verticals", "sectors")
- Geographic focus → platform_geographies
- Investment strategies / stages → transaction_types (NOT "investment_stages", "strategies")
- AUM / fund size → investment_capital_aum (ALWAYS "[REQUIRES EXTERNAL]")
- Comments / observations → notes (NOT "extraction_notes" or "comments")

OTHER RULES:
1. Extract ONLY what is explicitly stated on the provided HTML.
2. For ALL [REQUIRES EXTERNAL]-marked fields, emit the literal string; do NOT extract numerical values even if visible (PE firms occasionally publish AUM on homepage; client wants this from PitchBook with date stamp, not website snapshot).
3. Return JSON only, no prose, no markdown fences.

INPUT HTML FORMAT (Module 1.5+):
The HTML contains multiple page sections separated by HTML comments:
  <!-- ===== HOMEPAGE: https://... ===== -->
  <!-- ===== ABOUT: https://.../about ===== -->
  <!-- ===== TEAM: https://.../team ===== -->
  <!-- ===== CONTACT: https://.../contact ===== -->
  <!-- ===== PORTFOLIO: https://.../portfolio ===== -->
Use ALL sections. CONTACT → hq_location; TEAM → key_contacts; ABOUT → firm_type / notes / revenue_model_preference; PORTFOLIO → platform_industries / transaction_types.
"""

USER_PROMPT_TEMPLATE = """Firm to extract:
- Provided firm_name (from input list, may be canonical): {firm_name}
- Provided website (from input list): {website}

HTML content (truncated to 50K chars; multi-page concat per HOMEPAGE/ABOUT/TEAM/CONTACT/PORTFOLIO sections):
---
{html_truncated}
---

Output JSON matching FirmRecord schema.
"""


@dataclass
class ExtractionResult:
    record: FirmRecord | None
    raw_json: str | None
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class LLMExtractor:
    """Sync API extractor used by pilot mode. Batch API mode is a separate class (TODO Module 4)."""

    # OpenAI-compatible providers: same SDK, different base_url + api_key env var
    _OPENAI_COMPATIBLE = {
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "default_model_env": "MNA_DEEPSEEK_MODEL",
            "default_model": "deepseek-chat",
        },
        "openai": {
            "base_url": None,  # SDK default
            "api_key_env": "OPENAI_API_KEY",
            "default_model_env": "MNA_OPENAI_MODEL",
            "default_model": "gpt-4o-mini",
        },
    }

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
    ):
        self.provider = provider or os.getenv("MNA_LLM_PROVIDER", "deepseek")
        if self.provider in self._OPENAI_COMPATIBLE:
            cfg = self._OPENAI_COMPATIBLE[self.provider]
            self.model = model or os.getenv(cfg["default_model_env"], cfg["default_model"])
        elif self.provider == "anthropic":
            self.model = model or os.getenv(
                "MNA_ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def extract(
        self, firm_name: str, website: str, html: str
    ) -> ExtractionResult:
        html_truncated = html[:50_000]
        user_prompt = USER_PROMPT_TEMPLATE.format(
            firm_name=firm_name, website=website, html_truncated=html_truncated
        )

        if self.provider in self._OPENAI_COMPATIBLE:
            return self._extract_openai_compatible(
                user_prompt, firm_name, website, self._OPENAI_COMPATIBLE[self.provider]
            )
        return self._extract_anthropic(user_prompt, firm_name, website)

    def _extract_openai_compatible(
        self,
        user_prompt: str,
        firm_name: str,
        website: str,
        cfg: dict,
    ) -> ExtractionResult:
        """Shared path for OpenAI / DeepSeek (same SDK + JSON mode + temperature=0)."""
        try:
            from openai import OpenAI
        except ImportError:
            return ExtractionResult(
                record=None,
                raw_json=None,
                error="openai SDK not installed; pip install openai",
            )

        api_key = os.getenv(cfg["api_key_env"])
        if not api_key:
            return ExtractionResult(
                record=None,
                raw_json=None,
                error=f"{cfg['api_key_env']} not set",
            )

        client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            raw = resp.choices[0].message.content or "{}"
            data = json.loads(raw)
            data.setdefault("firm_name", firm_name)
            data.setdefault("website", website)
            record = FirmRecord.model_validate(data)
            usage = resp.usage
            return ExtractionResult(
                record=record,
                raw_json=raw,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            )
        except Exception as exc:
            return ExtractionResult(
                record=None,
                raw_json=None,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _extract_anthropic(
        self, user_prompt: str, firm_name: str, website: str
    ) -> ExtractionResult:
        # TODO Module 2 实测时启用：Anthropic SDK + tool use for structured output
        return ExtractionResult(
            record=None,
            raw_json=None,
            error="Anthropic provider not yet implemented (TODO Module 2)",
        )
