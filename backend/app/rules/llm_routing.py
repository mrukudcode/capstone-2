"""
Rule routing configuration.

LLM:
    Used when policy interpretation requires semantic reasoning.

Deterministic:
    Used when the rule can be evaluated directly from structured
    claim fields using arithmetic, dates, or exact comparisons.
"""


# ================================================================
# SEMANTIC / LLM RULES
# ================================================================

LLM_RULE_TYPES = {
    "EXCLUSION",
    "NON_COVERED_TREATMENT",
    "ELIGIBILITY_FAILURE",
    "DOCUMENTATION_MISSING",

    "POLICY_VERSION_RULE",
}


# ================================================================
# DETERMINISTIC RULES
# ================================================================

DETERMINISTIC_RULE_TYPES = {

    # ------------------------------------------------------------
    # FINANCIAL
    # ------------------------------------------------------------

    "ROOM_RENT_LIMIT",
    "ROOM_RENT",

    "SUB_LIMIT",
    "SUBLIMIT",

    "CO_PAYMENT",
    "COPAY",

    "DEDUCTIBLE",

    # ------------------------------------------------------------
    # WAITING PERIODS
    #
    # These are deterministic ONLY when the required dates and
    # waiting-period value are available.
    # ------------------------------------------------------------

    "PED_WAITING_PERIOD",

    # ------------------------------------------------------------
    # CLAIM TIMING
    # ------------------------------------------------------------

    "CLAIM_FILING_DEADLINE",
    "CLAIM_NOTIFICATION_DEADLINE",

    # ------------------------------------------------------------
    # PREAUTHORIZATION
    # ------------------------------------------------------------

    "PREAUTH_REQUIREMENT",
}


def should_use_llm(rule_type: str) -> bool:

    rule_type = str(
        rule_type or ""
    ).strip().upper()

    return rule_type in LLM_RULE_TYPES


def should_use_deterministic(rule_type: str) -> bool:

    rule_type = str(
        rule_type or ""
    ).strip().upper()

    return rule_type in DETERMINISTIC_RULE_TYPES