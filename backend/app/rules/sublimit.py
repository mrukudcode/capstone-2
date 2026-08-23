"""
SUB_LIMIT evaluator.

Active rules: SA26-006 (Home Care Treatment, 10% of SI max Rs.5 lakhs),
SA26-007 (Air Ambulance, 10% of SI, no separate cap stated).

Only fires when claim.treatment_category matches the rule's applies_to
text (case-insensitive substring), and claim.category_billed_amount and
claim.sum_insured are provided.
"""
from app.rules.common import parse_number, result


def _extract_abs_cap(unit: str):
    """Return an absolute rupee cap if the unit string encodes one, else None.
    NOTE: does NOT parse the percentage here -- the percentage always comes
    from rule.value. A prior version of this function incorrectly parsed the
    percentage out of the unit string itself, which for a unit like
    'PERCENT_OF_SUM_INSURED_MAX_RS_5_LAKHS' picks up the '5' from '5_LAKHS'
    instead of the real 10% in rule.value -- a real bug caught by
    tests/test_rule_engine.py::test_sublimit_home_care_boundary and fixed here.
    """
    unit = (unit or "").upper()
    if "MAX_RS_5_LAKHS" in unit:
        return 500000
    return None


def evaluate_sublimits(rules, claim):
    results = []
    for rule in rules:
        if rule.rule_type != "SUB_LIMIT":
            continue
        if not claim.treatment_category:
            continue
        if claim.treatment_category.strip().lower() not in (rule.applies_to or "").lower():
            continue
        if claim.category_billed_amount is None or claim.sum_insured is None:
            results.append(result(
                rule, "WARNING",
                f"Sub-limit rule applies to claim's treatment_category "
                f"({claim.treatment_category!r}) but category_billed_amount and/or "
                f"sum_insured were not provided -- cannot evaluate.",
                expected=f"{rule.value}{rule.unit}",
                actual="NOT_PROVIDED",
            ))
            continue

        pct = parse_number(rule.value)
        abs_cap = _extract_abs_cap(rule.unit)
        limit = float(claim.sum_insured) * (pct / 100.0)
        if abs_cap is not None:
            limit = min(limit, abs_cap)

        billed = float(claim.category_billed_amount)
        if billed <= limit:
            results.append(result(
                rule, "PASS",
                f"{claim.treatment_category} billed amount Rs.{billed} is within the "
                f"sub-limit of Rs.{limit:.2f}.",
                expected=f"<= Rs.{limit:.2f}",
                actual=f"Rs.{billed}",
            ))
        else:
            results.append(result(
                rule, "PARTIAL_DEDUCTION",
                f"{claim.treatment_category} billed amount Rs.{billed} exceeds the "
                f"sub-limit of Rs.{limit:.2f}. Amount above the sub-limit is not payable "
                f"under this cover.",
                expected=f"<= Rs.{limit:.2f}",
                actual=f"Rs.{billed}",
            ))
    return results
