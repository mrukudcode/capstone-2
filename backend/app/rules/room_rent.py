"""
ROOM_RENT_LIMIT evaluator.

Deterministic evaluator for room-rent limits.

Responsibilities
----------------
1. Determine whether a room-rent rule applies to the claim.
2. Calculate the allowed room rent per day.
3. Compare the claimed room rent against the allowed amount.
4. Return an exact proportion/admissible fraction when the limit is exceeded.

Important
---------
This evaluator does NOT decide insurer approval/rejection.

It only determines the mathematical consequence of the extracted
room-rent rule.

For room-rent limits, the exact proportionate deduction of associated
medical expenses depends on the policy wording. Therefore:

- The evaluator calculates the admissible room-rent fraction.
- It does NOT assume that every component of the claim is reduced
  proportionately.
- The financial calculator can use the fraction only where the
  policy/evaluator explicitly supports it.
"""

from app.rules.common import parse_number, result


# ================================================================
# HELPERS
# ================================================================

def _to_float(value):
    """
    Safely convert a numeric claim/rule value to float.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_sum_insured_band(sum_insured, allowed_bands):
    """
    Check whether the claim's Sum Insured belongs to one of the
    explicitly supported bands.

    Example:
        500000   -> 5 Lakh
        750000   -> 7.5 Lakh
    """

    if sum_insured is None:
        return False

    si_lakhs = sum_insured / 100000.0

    return any(
        abs(si_lakhs - band) < 0.01
        for band in allowed_bands
    )


# ================================================================
# ROOM RENT EVALUATOR
# ================================================================

def evaluate_room_rent(rules, claim):

    results = []

    for rule in rules:

        # --------------------------------------------------------
        # Only room-rent rules belong here.
        # --------------------------------------------------------

        if rule.rule_type != "ROOM_RENT_LIMIT":
            continue

        # --------------------------------------------------------
        # This evaluator currently handles percentage-of-SI/day
        # rules only.
        # --------------------------------------------------------

        if rule.unit != "PERCENT_OF_SUM_INSURED_PER_DAY":
            continue

        # --------------------------------------------------------
        # Required claim data
        # --------------------------------------------------------

        sum_insured = _to_float(
            claim.sum_insured
        )

        room_rent = _to_float(
            claim.room_rent_per_day
        )

        if sum_insured is None or room_rent is None:

            results.append(
                result(
                    rule,
                    "WARNING",

                    (
                        "Room rent limit rule exists for this "
                        "policy version, but the claim is missing "
                        "sum_insured and/or room_rent_per_day. "
                        "The rule cannot be evaluated automatically."
                    ),

                    expected=(
                        f"{rule.value}% of Sum Insured per day"
                    ),

                    actual="NOT_PROVIDED",
                )
            )

            continue

        # --------------------------------------------------------
        # POLICY-SPECIFIC BAND
        #
        # SA26-005 applies to the 5L / 7.5L bands.
        #
        # 10L+ is explicitly outside this rule because the policy
        # states "Any Room".
        # --------------------------------------------------------

        supported_bands = [
            5.0,
            7.5,
        ]

        if not _is_sum_insured_band(
            sum_insured,
            supported_bands,
        ):

            # Rule does not apply.
            #
            # Important:
            # Do NOT return PASS because the rule simply does not
            # govern this claim's SI band.
            continue

        # --------------------------------------------------------
        # CALCULATE ROOM RENT LIMIT
        # --------------------------------------------------------

        pct = parse_number(
            rule.value
        )

        if pct is None:

            results.append(
                result(
                    rule,
                    "WARNING",

                    (
                        "Room rent rule contains an invalid "
                        "percentage value and cannot be evaluated "
                        "deterministically."
                    ),

                    expected=(
                        f"Valid percentage value, received: {rule.value}"
                    ),

                    actual="INVALID_RULE_VALUE",
                )
            )

            continue

        limit_per_day = (
            sum_insured
            * pct
            / 100.0
        )

        # --------------------------------------------------------
        # ROOM RENT WITHIN LIMIT
        # --------------------------------------------------------

        if room_rent <= limit_per_day:

            results.append(
                result(
                    rule,
                    "PASS",

                    (
                        f"Room rent Rs.{room_rent:.2f}/day is within "
                        f"the {pct}% of Sum Insured/day limit "
                        f"(Rs.{limit_per_day:.2f}/day)."
                    ),

                    expected=(
                        f"<= Rs.{limit_per_day:.2f}/day"
                    ),

                    actual=(
                        f"Rs.{room_rent:.2f}/day"
                    ),
                )
            )

            continue

        # --------------------------------------------------------
        # ROOM RENT EXCEEDS LIMIT
        # --------------------------------------------------------

        admissible_fraction = (
            limit_per_day
            / room_rent
        )

        deduction_fraction = (
            1.0
            - admissible_fraction
        )

        results.append(
            result(
                rule,
                "PARTIAL_DEDUCTION",

                (
                    f"Room rent Rs.{room_rent:.2f}/day exceeds "
                    f"the permitted {pct}% of Sum Insured/day "
                    f"limit of Rs.{limit_per_day:.2f}/day. "
                    f"The calculated admissible room-rent fraction "
                    f"is {admissible_fraction:.4f} "
                    f"({admissible_fraction * 100:.2f}%). "
                    f"The corresponding excess fraction is "
                    f"{deduction_fraction:.4f} "
                    f"({deduction_fraction * 100:.2f}%). "
                    f"Any proportionate reduction of associated "
                    f"medical expenses must be applied only where "
                    f"the applicable policy wording supports it."
                ),

                expected=(
                    f"<= Rs.{limit_per_day:.2f}/day"
                ),

                actual=(
                    f"Rs.{room_rent:.2f}/day"
                ),
            )
        )

    return results