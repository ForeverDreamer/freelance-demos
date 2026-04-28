"""Pydantic v2 output schema for M&A buyer firm extraction.

Mirrors the client's exact 33-column Buyer Database format (case.md §4.2 + actual
Buyers_Database_Final3.xlsx inspection 2026-04-28).

Excel section grouping:
- FIRM IDENTITY (5 cols): firm_name, firm_type, website, hq_location, key_contacts
- INVESTMENT OVERVIEW (6 cols): investment_capital_aum, ev_min_m, ev_max_m,
  revenue_model_preference, preferred_ebitda_margin_min, hold_period_strategy
- PLATFORM SEARCH CRITERIA (7 cols): platform_industries, platform_geographies,
  platform_ebitda_min_k, platform_ebitda_max_m, platform_revenue_min_m,
  platform_revenue_max_m, platform_additional_criteria
- ADD-ON SEARCH CRITERIA (8 cols): addon_industries, addon_geographies,
  addon_ebitda_min_k, addon_ebitda_max_m, addon_revenue_min_m, addon_revenue_max_m,
  addon_opportunistic, addon_additional_criteria
- DEAL STRUCTURE (3 cols): transaction_types, min_ownership_pct, typical_debt_leverage
- META (4 cols): source_urls, date_researched, confidence_level, notes

PE-internal numerical fields (cannot be extracted from public website) emit the
literal string "[REQUIRES EXTERNAL]" marker.
"""

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class FirmType(str, Enum):
    """Aligned with client's 'Firm Type' column enum."""

    PRIVATE_EQUITY = "Private Equity"
    SEARCH_FUND = "Search Fund"
    FAMILY_OFFICE = "Family Office"
    STRATEGIC = "Strategic"
    SBIC = "SBIC"
    GROWTH_EQUITY = "Growth Equity"
    HOLDCO = "HoldCo"
    INDEPENDENT_SPONSOR = "Independent Sponsor"
    UNKNOWN = "Unknown"


# Marker constant for fields that cannot be extracted from public website.
EXTERNAL_REQUIRED = "[REQUIRES EXTERNAL: PitchBook / Grata / 2-Pager PDF]"


class KeyContact(BaseModel):
    name: str | None = None
    title: str | None = None
    email: str | None = None


# Field name -> Excel column name (display label) mapping. Used by excel_writer.
# Also doubles as the canonical 33-column ordered field list.
EXCEL_COLUMN_LABELS: dict[str, str] = {
    # FIRM IDENTITY
    "firm_name": "Firm Name",
    "firm_type": "Firm Type",
    "website": "Website",
    "hq_location": "HQ Location",
    "key_contacts": "Key Contact(s)",
    # INVESTMENT OVERVIEW
    "investment_capital_aum": "Investment Capital / AUM",
    "ev_min_m": "EV Min ($M)",
    "ev_max_m": "EV Max ($M)",
    "revenue_model_preference": "Revenue Model Preference",
    "preferred_ebitda_margin_min": "Preferred EBITDA Margin Min",
    "hold_period_strategy": "Hold Period / Strategy",
    # PLATFORM SEARCH CRITERIA
    "platform_industries": "Platform: Industries / Verticals",
    "platform_geographies": "Platform: Geographies",
    "platform_ebitda_min_k": "Platform: EBITDA Min ($K)",
    "platform_ebitda_max_m": "Platform: EBITDA Max ($M)",
    "platform_revenue_min_m": "Platform: Revenue Min ($M)",
    "platform_revenue_max_m": "Platform: Revenue Max ($M)",
    "platform_additional_criteria": "Platform: Additional Criteria",
    # ADD-ON SEARCH CRITERIA
    "addon_industries": "Add-On: Industries / Verticals (Restricted to Platforms)",
    "addon_geographies": "Add-On: Geographies (Restricted to Platform Footprints)",
    "addon_ebitda_min_k": "Add-On: EBITDA Min ($K)",
    "addon_ebitda_max_m": "Add-On: EBITDA Max ($M)",
    "addon_revenue_min_m": "Add-On: Revenue Min ($M)",
    "addon_revenue_max_m": "Add-On: Revenue Max ($M)",
    "addon_opportunistic": "Add-On: Opportunistic? (Any Industry if EBITDA ≥ threshold)",
    "addon_additional_criteria": "Add-On: Additional Criteria",
    # DEAL STRUCTURE
    "transaction_types": "Transaction Types",
    "min_ownership_pct": "Min Ownership %",
    "typical_debt_leverage": "Typical Debt / Leverage",
    # META
    "source_urls": "Source URL(s)",
    "date_researched": "Date Researched",
    "confidence_level": "Confidence Level",
    "notes": "Notes / Comments",
}

# Section -> list of field names. Used by excel_writer for section headers.
EXCEL_SECTIONS: list[tuple[str, list[str]]] = [
    ("FIRM IDENTITY", ["firm_name", "firm_type", "website", "hq_location", "key_contacts"]),
    (
        "INVESTMENT OVERVIEW",
        [
            "investment_capital_aum", "ev_min_m", "ev_max_m",
            "revenue_model_preference", "preferred_ebitda_margin_min", "hold_period_strategy",
        ],
    ),
    (
        "PLATFORM SEARCH CRITERIA",
        [
            "platform_industries", "platform_geographies",
            "platform_ebitda_min_k", "platform_ebitda_max_m",
            "platform_revenue_min_m", "platform_revenue_max_m",
            "platform_additional_criteria",
        ],
    ),
    (
        "ADD-ON SEARCH CRITERIA",
        [
            "addon_industries", "addon_geographies",
            "addon_ebitda_min_k", "addon_ebitda_max_m",
            "addon_revenue_min_m", "addon_revenue_max_m",
            "addon_opportunistic", "addon_additional_criteria",
        ],
    ),
    ("DEAL STRUCTURE", ["transaction_types", "min_ownership_pct", "typical_debt_leverage"]),
    ("META", ["source_urls", "date_researched", "confidence_level", "notes"]),
]


class FirmRecord(BaseModel):
    """One row of output. Maps 1:1 to client's 33-column Buyer Database."""

    # FIRM IDENTITY
    firm_name: str
    firm_type: FirmType = FirmType.UNKNOWN
    website: HttpUrl
    hq_location: str | None = Field(
        default=None, description="City, State/Province | Country"
    )
    key_contacts: list[KeyContact] = Field(default_factory=list)

    # INVESTMENT OVERVIEW
    investment_capital_aum: str = EXTERNAL_REQUIRED
    ev_min_m: str = EXTERNAL_REQUIRED
    ev_max_m: str = EXTERNAL_REQUIRED
    revenue_model_preference: str | None = Field(
        default=None,
        description="Recurring vs project-based vs mixed; LLM-inferable from website tone",
    )
    preferred_ebitda_margin_min: str = EXTERNAL_REQUIRED
    hold_period_strategy: str = EXTERNAL_REQUIRED

    # PLATFORM SEARCH CRITERIA
    platform_industries: list[str] = Field(
        default_factory=list,
        description="Free-text industries firm targets for platform investments",
    )
    platform_geographies: list[str] = Field(default_factory=list)
    platform_ebitda_min_k: str = EXTERNAL_REQUIRED
    platform_ebitda_max_m: str = EXTERNAL_REQUIRED
    platform_revenue_min_m: str = EXTERNAL_REQUIRED
    platform_revenue_max_m: str = EXTERNAL_REQUIRED
    platform_additional_criteria: str | None = Field(
        default=None,
        description="Free-text Platform criteria (e.g. 'recession-resistant', 'recurring revenue')",
    )

    # ADD-ON SEARCH CRITERIA
    addon_industries: list[str] = Field(
        default_factory=list,
        description="Add-on industries (typically a subset of platform_industries)",
    )
    addon_geographies: list[str] = Field(default_factory=list)
    addon_ebitda_min_k: str = EXTERNAL_REQUIRED
    addon_ebitda_max_m: str = EXTERNAL_REQUIRED
    addon_revenue_min_m: str = EXTERNAL_REQUIRED
    addon_revenue_max_m: str = EXTERNAL_REQUIRED
    addon_opportunistic: str | None = Field(
        default=None,
        description="Yes/No + threshold; e.g. 'Yes - if EBITDA >= $5M'",
    )
    addon_additional_criteria: str | None = None

    # DEAL STRUCTURE
    transaction_types: list[str] = Field(
        default_factory=list,
        description="e.g. Buyout / Growth Equity / Carve-out / Recap",
    )
    min_ownership_pct: str = EXTERNAL_REQUIRED
    typical_debt_leverage: str = EXTERNAL_REQUIRED

    # META
    source_urls: list[HttpUrl] = Field(
        default_factory=list,
        description="Pages used during extraction; populated by pipeline post-extraction",
    )
    date_researched: str | None = None
    confidence_level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    notes: str | None = Field(
        default=None,
        description="Free-form salient observations + extraction caveats",
    )


class ExtractionRunStats(BaseModel):
    """Aggregate stats per pipeline run, for cost / accuracy reporting."""

    total_firms_attempted: int = 0
    total_firms_succeeded: int = 0
    total_firms_fetch_failed: int = 0
    total_firms_llm_failed: int = 0

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0

    elapsed_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_firms_attempted == 0:
            return 0.0
        return self.total_firms_succeeded / self.total_firms_attempted
