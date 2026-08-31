"""
PREAUTH_REQUIREMENT evaluator.

Evaluates only policyholder-side preauthorization lead-time rules
that can be verified from claim data.

Insurer-side TAT rules are intentionally not evaluated because
they describe insurer obligations rather than claim facts.
"""

from datetime import datetime

from app.rules.common import parse_hours, result


def _to_hours(later, earlier):
    """
    Return the exact elapsed time in hours.

    Works with datetime values and date-like values.
    """

    if later is None or earlier is None:
        return None

    try:
        difference = later - earlier

        if hasattr(difference, "total_seconds"):
            return difference.total_seconds() / 3600.0

        return difference.days * 24.0

    except Exception:
        return None


def evaluate_preauth(rules, claim):

    results = []

    for rule in rules:

        if str(rule.rule_type or "").upper() != "PREAUTH_REQUIREMENT":
            continue

        applies = str(
            rule.applies_to or ""
        ).lower()

        # --------------------------------------------------------
        # Only planned-hospitalization lead-time rules are
        # evaluable from claim-side data.
        # --------------------------------------------------------

        if "planned" not in applies:
            continue

        # --------------------------------------------------------
        # Rule does not apply to emergency hospitalization.
        # --------------------------------------------------------

        if str(
            claim.claim_type or ""
        ).upper() != "PLANNED":
            continue

        # --------------------------------------------------------
        # Required claim data
        # --------------------------------------------------------

        if (
            claim.preauth_request_date is None
            or claim.admission_date is None
        ):

            results.append(
                result(
                    rule,
                    "WARNING",

                    (
                        "Planned-hospitalization preauthorization "
                        "lead-time rule applies, but "
                        "preauth_request_date and/or admission_date "
                        "was not provided. The requirement cannot "
                        "be verified."
                    ),

                    expected=(
                        f">= {rule.value} {rule.unit} "
                        "before admission"
                    ),

                    actual="NOT_PROVIDED",
                )
            )

            continue

        # --------------------------------------------------------
        # Convert policy requirement
        # --------------------------------------------------------

        limit_hours = parse_hours(
            rule.value,
            rule.unit
        )

        if limit_hours is None:
            results.append(
                result(
                    rule,
                    "WARNING",

                    (
                        "Preauthorization rule could not be "
                        "evaluated because the policy time limit "
                        "could not be parsed."
                    ),

                    expected=(
                        f">= {rule.value} {rule.unit}"
                    ),

                    actual="INVALID_POLICY_TIME_LIMIT",
                )
            )

            continue

        # --------------------------------------------------------
        # Exact elapsed time
        # --------------------------------------------------------

        lead_hours = _to_hours(
            claim.admission_date,
            claim.preauth_request_date
        )

        if lead_hours is None:
            results.append(
                result(
                    rule,
                    "WARNING",

                    (
                        "Preauthorization lead time could not "
                        "be calculated from the supplied dates."
                    ),

                    expected=(
                        f">= {rule.value} {rule.unit} "
                        "before admission"
                    ),

                    actual="INVALID_DATE_DATA",
                )
            )

            continue

        # --------------------------------------------------------
        # PASS
        # --------------------------------------------------------

        if lead_hours >= limit_hours:

            results.append(
                result(
                    rule,
                    "PASS",

                    (
                        f"Preauthorization was requested "
                        f"{lead_hours:.1f} hours before admission, "
                        f"meeting the {rule.value} {rule.unit} "
                        "requirement for planned hospitalization."
                    ),

                    expected=(
                        f">= {rule.value} {rule.unit}"
                    ),

                    actual=(
                        f"{lead_hours:.1f} hours"
                    ),
                )
            )

        # --------------------------------------------------------
        # WARNING
        # --------------------------------------------------------

        else:

            results.append(
                result(
                    rule,
                    "WARNING",

                    (
                        f"Preauthorization was requested only "
                        f"{lead_hours:.1f} hours before admission, "
                        f"short of the {rule.value} {rule.unit} "
                        "requirement for planned hospitalization. "
                        "Cashless facility may be at risk; "
                        "reimbursement may still be available."
                    ),

                    expected=(
                        f">= {rule.value} {rule.unit}"
                    ),

                    actual=(
                        f"{lead_hours:.1f} hours"
                    ),
                )
            )

    return results