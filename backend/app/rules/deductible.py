"""
DEDUCTIBLE evaluator.

Active rule: SA26-009 -- OPTIONAL aggregate deductible, only applicable if
the policyholder chose it (Rs.50,000 or Rs.1,00,000 for Sum Insured up to
Rs.20 lakhs). Per the rule's own exception text: "Only if opted; not
automatic." This evaluator therefore does nothing unless
claim.deductible_opted is True.
"""
from app.rules.common import result


def evaluate_deductible(rules, claim):
    results = []
    for rule in rules:
        if rule.rule_type != "DEDUCTIBLE":
            continue
        if not claim.deductible_opted:
            # Correctly not applicable -- this is an optional cover, not a
            # default policy term. No result emitted (not a fabricated PASS).
            continue
        if claim.deductible_amount_opted is None or claim.billed_amount is None:
            results.append(result(
                rule, "WARNING",
                "deductible_opted=True but deductible_amount_opted and/or billed_amount "
                "were not provided -- cannot evaluate.",
                expected=rule.value,
                actual="NOT_PROVIDED",
            ))
            continue

        allowed_amounts = {50000.0, 100000.0}
        if float(claim.deductible_amount_opted) not in allowed_amounts:
            results.append(result(
                rule, "WARNING",
                f"deductible_amount_opted Rs.{claim.deductible_amount_opted} does not match "
                f"either of the two Sum-Insured-up-to-Rs.20-Lakhs options in the source text "
                f"(Rs.50,000 or Rs.1,00,000) -- flag for human review.",
                expected="Rs.50,000 or Rs.1,00,000",
                actual=f"Rs.{claim.deductible_amount_opted}",
            ))
            continue

        deductible_amt = float(claim.deductible_amount_opted)
        billed = float(claim.billed_amount)
        remaining = max(billed - deductible_amt, 0)
        results.append(result(
            rule, "PARTIAL_DEDUCTION",
            f"Opted aggregate deductible of Rs.{deductible_amt} applies once per Policy Year "
            f"before Company liability commences. Rs.{deductible_amt} deducted from billed "
            f"Rs.{billed}, leaving Rs.{remaining:.2f} before other adjustments.",
            expected=f"Deduct Rs.{deductible_amt}",
            actual=f"Rs.{remaining:.2f} remaining after deductible",
        ))
    return results
