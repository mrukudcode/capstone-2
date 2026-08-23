"""
CO_PAYMENT evaluator.

Active rule: SA26-008 -- 10% co-pay on every claim for Star Assure
policyholders whose age AT ENTRY is 61 years or above. This is an
entry-age condition, not current age, per the source text ("age at the
time of entry").
"""
from app.rules.common import parse_number, result


def evaluate_copay(rules, claim):
    results = []
    for rule in rules:
        if rule.rule_type != "CO_PAYMENT":
            continue
        if claim.insured_age_at_entry is None or claim.billed_amount is None:
            results.append(result(
                rule, "WARNING",
                "Co-payment rule exists for this policy version but claim is missing "
                "insured_age_at_entry and/or billed_amount -- cannot evaluate.",
                expected=f"{rule.value}% co-pay if entry age >= threshold",
                actual="NOT_PROVIDED",
            ))
            continue

        # Threshold is embedded in rule.condition, e.g. "Insured person age at
        # entry 61 years and above". Extract the age number deterministically.
        age_threshold = parse_number(rule.condition)
        if age_threshold is None:
            results.append(result(
                rule, "WARNING",
                f"Could not parse an age threshold from condition text {rule.condition!r} "
                f"-- flag for human review rather than guess.",
                expected=rule.condition,
                actual=f"age_at_entry={claim.insured_age_at_entry}",
            ))
            continue

        pct = parse_number(rule.value)
        if claim.insured_age_at_entry >= age_threshold:
            copay_amount = float(claim.billed_amount) * (pct / 100.0)
            results.append(result(
                rule, "PARTIAL_DEDUCTION",
                f"Insured age at entry ({claim.insured_age_at_entry}) meets the "
                f"{int(age_threshold)}+ threshold; {pct}% co-payment of Rs.{copay_amount:.2f} "
                f"applies to this claim.",
                expected=f"{pct}% co-pay",
                actual=f"Rs.{copay_amount:.2f} on billed Rs.{claim.billed_amount}",
            ))
        else:
            results.append(result(
                rule, "PASS",
                f"Insured age at entry ({claim.insured_age_at_entry}) is below the "
                f"{int(age_threshold)} threshold; co-payment rule does not apply.",
                expected=f"No co-pay below age {int(age_threshold)}",
                actual=f"age_at_entry={claim.insured_age_at_entry}",
            ))
    return results
