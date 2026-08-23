"""
PREAUTH_REQUIREMENT evaluator.

Only the POLICYHOLDER-SIDE rule (SA26-013: planned hospitalization must be
notified/preauth-requested at least 48 hours before treatment) is
evaluable from claim data. The insurer-side TAT rules (SA26-020,
IRDAI-002, IRDAI-003 -- 1hr/3hr response times) describe insurer
obligations, not something a submitted claim's own fields can verify;
they are intentionally NOT evaluated here to avoid fabricating a
pass/fail on data the claim doesn't and can't contain.
"""
from app.rules.common import parse_hours, result


def evaluate_preauth(rules, claim):
    results = []
    for rule in rules:
        if rule.rule_type != "PREAUTH_REQUIREMENT":
            continue
        applies = (rule.applies_to or "").lower()
        if "planned" not in applies:
            continue  # insurer-side TAT rules -- not evaluable from claim fields
        if (claim.claim_type or "").upper() != "PLANNED":
            continue
        if claim.preauth_request_date is None or claim.admission_date is None:
            results.append(result(
                rule, "WARNING",
                "Planned-hospitalization preauth-lead-time rule applies but "
                "preauth_request_date and/or admission_date not provided -- cannot evaluate.",
                expected=f">= {rule.value} {rule.unit} before admission",
                actual="NOT_PROVIDED",
            ))
            continue
        limit_hours = parse_hours(rule.value, rule.unit)
        lead_hours = (claim.admission_date - claim.preauth_request_date).days * 24.0
        if limit_hours is None:
            continue
        if lead_hours >= limit_hours:
            results.append(result(
                rule, "PASS",
                f"Preauthorization requested {lead_hours:.0f} hours before admission, "
                f"meeting the {rule.value} {rule.unit} requirement for planned hospitalization.",
                expected=f">= {rule.value} {rule.unit}",
                actual=f"{lead_hours:.0f} hours",
            ))
        else:
            results.append(result(
                rule, "WARNING",
                f"Preauthorization requested only {lead_hours:.0f} hours before admission, "
                f"short of the {rule.value} {rule.unit} requirement for planned hospitalization. "
                f"Cashless facility may be at risk; reimbursement route may still be available.",
                expected=f">= {rule.value} {rule.unit}",
                actual=f"{lead_hours:.0f} hours",
            ))
    return results
