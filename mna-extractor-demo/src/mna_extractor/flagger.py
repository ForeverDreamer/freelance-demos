"""Confidence rubric + [REQUIRES EXTERNAL] flag logic.

TODO during 实测 Module 6 (case.md §5.2 #6):
- Calibrate confidence rubric thresholds against 200-500 row sampled QA results
- Decide whether to auto-downgrade Medium -> Low when source_urls list is < 2
"""

from __future__ import annotations

from .schema import ConfidenceLevel, FirmRecord


def assign_confidence(record: FirmRecord) -> ConfidenceLevel:
    """Assign confidence level based on field coverage.

    Rubric:
    - High = firm_name + website + HQ + >= 1 industry, all explicitly on website
    - Medium = firm_name + website + (HQ OR >= 1 industry); other lacks evidence
    - Low = neither HQ nor industries extractable; firm_name + website only

    Note: source_urls >= 2 used to be required for High but is now redundant given
    Module 1.5 multi-page fetch always returns 2-4 URLs per firm. Dropping it lets
    the rubric focus on field-level data completeness, which is the real demo signal.
    """
    has_hq = bool(record.hq_location)
    has_industries = len(record.platform_industries) > 0

    if has_hq and has_industries:
        return ConfidenceLevel.HIGH
    if has_hq or has_industries:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def post_process(record: FirmRecord) -> FirmRecord:
    """Apply confidence level + ensure all Category C fields stay flagged external.

    Defends against LLM hallucinating values into PE-internal fields. Any value
    that doesn't start with [REQUIRES EXTERNAL is reset to the marker constant.
    """
    from .schema import EXTERNAL_REQUIRED

    external_fields = [
        "investment_capital_aum",
        "ev_min_m",
        "ev_max_m",
        "platform_ebitda_min_k",
        "platform_ebitda_max_m",
        "platform_revenue_min_m",
        "platform_revenue_max_m",
        "addon_ebitda_min_k",
        "addon_ebitda_max_m",
        "addon_revenue_min_m",
        "addon_revenue_max_m",
        "preferred_ebitda_margin_min",
        "hold_period_strategy",
        "min_ownership_pct",
        "typical_debt_leverage",
    ]

    record_dict = record.model_dump()
    for field in external_fields:
        value = record_dict.get(field, "")
        if not isinstance(value, str) or not value.startswith("[REQUIRES EXTERNAL"):
            record_dict[field] = EXTERNAL_REQUIRED

    record_dict["confidence_level"] = assign_confidence(record).value

    return FirmRecord.model_validate(record_dict)
