"""
DOCUMENTATION_MISSING evaluator.

Active rule: HDFC21-011 -- KYC documents required for claims above Rs.1
lakh. Only fires when claim.billed_amount exceeds the rule's threshold
AND documents_submitted doesn't already list KYC.
"""
from app.rules.common import parse_number, result


def evaluate_documentation(rules, claim):
    results = []
    for rule in rules:
        if rule.rule_type != "DOCUMENTATION_MISSING":
            continue
        threshold = parse_number(rule.value)
        if threshold is None or claim.billed_amount is None:
            continue
        if float(claim.billed_amount) <= threshold:
            continue  # rule's own condition ("Claims above Rs 1 lakh") doesn't apply
        submitted = (claim.documents_submitted or "").lower()
        if "kyc" in submitted:
            results.append(result(
                rule, "PASS",
                f"Billed amount Rs.{claim.billed_amount} exceeds Rs.{threshold:.0f}; "
                f"KYC documentation was submitted as required.",
                expected="KYC documents present",
                actual="KYC present in documents_submitted",
            ))
        else:
            results.append(result(
                rule, "WARNING",
                f"Billed amount Rs.{claim.billed_amount} exceeds Rs.{threshold:.0f}, "
                f"triggering the KYC documentation requirement, but KYC was not found in "
                f"documents_submitted.",
                expected="KYC documents present",
                actual=claim.documents_submitted or "NONE_PROVIDED",
            ))
    return results
