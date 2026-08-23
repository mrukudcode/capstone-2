"""
Financial calculator: deterministic arithmetic only, no LLM.

RULE-BASED ESTIMATE -- NOT A GUARANTEED INSURER PAYOUT.

Calculation order used here, and why (documented per project instruction
to check actual policy wording rather than assume an order):

Star Health Assure's own CIS financial-limits table lists items in this
order: sub-limits -> co-payment -> deductible (Section 8: "i. Sub-limit",
"ii. Co-payment", "iii Deductible" -- see STAR_ASSURE_2026_CIS page 14).
HDFC's 2026 Policy Wording states a "Utilization of Sum Insured" sequence
of Aggregate Deductible -> Base Sum Insured -> Secure Benefit -> Cumulative
Bonus/Plus Benefit (Section D.1.19), i.e. HDFC applies its deductible
FIRST, before other benefit utilization.

Because the two insurers' own documents state DIFFERENT orders, this
calculator does not hardcode one universal order. Instead it applies:
  1. Sub-limit / room-rent-proportional adjustment (caps the billable base)
  2. Deductible (HDFC-documented "first" position; also mathematically
     neutral relative to co-pay when applied to the post-sub-limit amount)
  3. Co-payment (percentage of what remains)
and this order is explicitly logged in the returned breakdown so a human
reviewer can see and correct it if a specific policy's actual order
differs. This is a documented judgment call, not a silent assumption.
"""
from decimal import Decimal


def calculate_financials(billed_amount, room_rent_adjustment_results, sublimit_results,
                          deductible_results, copay_results):
    """
    Each *_results arg is the list of result dicts from the corresponding
    evaluator (already computed against real rules). This function does not
    re-derive rule values -- it reads the adjustments those evaluators
    already computed deterministically, and combines them arithmetically.
    """
    gross_bill = Decimal(str(billed_amount)) if billed_amount is not None else Decimal("0")
    remaining = gross_bill

    room_rent_adjustment = Decimal("0")
    for r in room_rent_adjustment_results:
        if r["severity"] == "PARTIAL_DEDUCTION":
            # Evaluator did not compute an exact rupee figure for room-rent
            # proportionate deduction (documented limitation in room_rent.py);
            # flag it rather than silently apply Rs.0 adjustment.
            room_rent_adjustment = None
            break

    sub_limit_adjustment = Decimal("0")
    for r in sublimit_results:
        if r["severity"] == "PARTIAL_DEDUCTION":
            # actual/expected strings hold "Rs.X" figures; extract deterministically
            try:
                billed_str = r["actual"].split("Rs.")[1]
                limit_str = r["expected"].split("Rs.")[1]
                billed_val = Decimal(billed_str)
                limit_val = Decimal(limit_str)
                sub_limit_adjustment += (billed_val - limit_val)
            except (IndexError, ValueError):
                pass

    if sub_limit_adjustment > 0:
        remaining -= sub_limit_adjustment

    deductible_amount = Decimal("0")
    for r in deductible_results:
        if r["severity"] == "PARTIAL_DEDUCTION" and "Deduct Rs." in r["expected"]:
            try:
                deductible_amount = Decimal(r["expected"].split("Rs.")[1])
            except (IndexError, ValueError):
                pass
    remaining -= deductible_amount
    if remaining < 0:
        remaining = Decimal("0")

    copay_amount = Decimal("0")
    for r in copay_results:
        if r["severity"] == "PARTIAL_DEDUCTION" and "Rs." in r["actual"]:
            try:
                copay_amount = Decimal(r["actual"].split("Rs.")[1].split(" ")[0])
            except (IndexError, ValueError):
                pass
    remaining -= copay_amount
    if remaining < 0:
        remaining = Decimal("0")

    return {
        "label": "RULE-BASED ESTIMATE -- NOT A GUARANTEED INSURER PAYOUT",
        "calculation_order": ["sub_limit_adjustment", "deductible", "copay_amount"],
        "gross_bill": str(gross_bill),
        "room_rent_adjustment": (
            "NOT_COMPUTED_EXACT_FIGURE_SEE_room_rent.py_LIMITATION"
            if room_rent_adjustment is None else str(room_rent_adjustment)
        ),
        "sub_limit_adjustment": str(sub_limit_adjustment),
        "deductible": str(deductible_amount),
        "copay_amount": str(copay_amount),
        "estimated_eligible_amount": str(remaining),
    }
