"""
CLAIM_FILING_DEADLINE and CLAIM_NOTIFICATION_DEADLINE evaluator.

Matches rules whose applies_to text does NOT mention "post" (i.e. the
primary hospitalization reimbursement filing deadline) against
claim.claim_filed_date - claim.discharge_date, and notification-deadline
rules whose applies_to mentions "Emergency" against
claim.notification_date - claim.admission_date, only when claim.claim_type
== "EMERGENCY". Rules that don't match a computable claim field pairing
are skipped, not fabricated.
"""
from app.rules.common import parse_hours, result
from datetime import datetime


def _to_hours(d1, d2):
    if d1 is None or d2 is None:
        return None
    return (d1 - d2).total_seconds() / 3600.0 if isinstance(d1, datetime) else \
        (d1 - d2).days * 24.0


def evaluate_deadlines(rules, claim):
    results = []
    for rule in rules:
        if rule.rule_type == "CLAIM_FILING_DEADLINE":
            if "post" in (rule.applies_to or "").lower():
                continue  # post-hospitalization variant not evaluable without a separate field
            if claim.claim_filed_date is None or claim.discharge_date is None:
                results.append(result(
                    rule, "WARNING",
                    "Claim filing deadline rule exists but claim_filed_date and/or "
                    "discharge_date not provided -- cannot evaluate.",
                    expected=f"<= {rule.value} {rule.unit} from discharge",
                    actual="NOT_PROVIDED",
                ))
                continue
            limit_hours = parse_hours(rule.value, rule.unit)
            actual_hours = _to_hours(claim.claim_filed_date, claim.discharge_date)
            if limit_hours is None or actual_hours is None:
                continue
            if actual_hours <= limit_hours:
                results.append(result(
                    rule, "PASS",
                    f"Claim filed {actual_hours/24:.1f} days after discharge, within the "
                    f"{rule.value} {rule.unit} deadline.",
                    expected=f"<= {rule.value} {rule.unit}",
                    actual=f"{actual_hours/24:.1f} days",
                ))
            else:
                results.append(result(
                    rule, "WARNING",
                    f"Claim filed {actual_hours/24:.1f} days after discharge, exceeding the "
                    f"{rule.value} {rule.unit} deadline. Late filing does not automatically "
                    f"disqualify a claim (insurers may condone genuine delay) -- flagged for "
                    f"human review rather than automatic FAIL.",
                    expected=f"<= {rule.value} {rule.unit}",
                    actual=f"{actual_hours/24:.1f} days",
                ))

        elif rule.rule_type == "CLAIM_NOTIFICATION_DEADLINE":
            if "emergency" not in (rule.applies_to or "").lower():
                continue
            if (claim.claim_type or "").upper() != "EMERGENCY":
                continue
            if claim.notification_date is None or claim.admission_date is None:
                results.append(result(
                    rule, "WARNING",
                    "Emergency notification deadline rule applies to this claim_type but "
                    "notification_date and/or admission_date not provided -- cannot evaluate.",
                    expected=f"<= {rule.value} {rule.unit} from admission",
                    actual="NOT_PROVIDED",
                ))
                continue
            limit_hours = parse_hours(rule.value, rule.unit)
            actual_hours = _to_hours(claim.notification_date, claim.admission_date)
            if limit_hours is None or actual_hours is None:
                continue
            if actual_hours <= limit_hours:
                results.append(result(
                    rule, "PASS",
                    f"Insurer notified {actual_hours:.1f} hours after admission, within the "
                    f"{rule.value} {rule.unit} requirement.",
                    expected=f"<= {rule.value} {rule.unit}",
                    actual=f"{actual_hours:.1f} hours",
                ))
            else:
                results.append(result(
                    rule, "WARNING",
                    f"Insurer notified {actual_hours:.1f} hours after admission, exceeding the "
                    f"{rule.value} {rule.unit} requirement for emergency hospitalization.",
                    expected=f"<= {rule.value} {rule.unit}",
                    actual=f"{actual_hours:.1f} hours",
                ))
    return results
