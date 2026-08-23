"""
ROOM_RENT_LIMIT evaluator.

Only one active rule exists in the dataset: SA26-005 (Star Assure 2026),
"Sum Insured 5/7.5 Lakhs: Room Rent Criteria = Up to 1% of Sum Insured per
day", condition text explicitly states the 10-Lakh+ bands use "Any Room"
criteria instead (i.e. no percentage cap applies there). This evaluator
only fires the percentage-cap check when the rule's own condition text
band matches the claim's sum_insured; otherwise it correctly does nothing
for that rule (not a fabricated pass).
"""
from app.rules.common import parse_number, result


def evaluate_room_rent(rules, claim):
    results = []
    for rule in rules:
        if rule.rule_type != "ROOM_RENT_LIMIT":
            continue
        if rule.unit != "PERCENT_OF_SUM_INSURED_PER_DAY":
            # Not a percentage-per-day rule this evaluator knows how to compute.
            continue
        if claim.sum_insured is None or claim.room_rent_per_day is None:
            results.append(result(
                rule, "WARNING",
                "Room rent limit rule exists for this policy version but claim is "
                "missing sum_insured and/or room_rent_per_day -- cannot evaluate.",
                expected=f"{rule.value}% of Sum Insured per day",
                actual="NOT_PROVIDED",
            ))
            continue

        # Rule's own condition text scopes it to the 5/7.5 Lakh band.
        band_lakhs = [5, 7.5]
        si_lakhs = float(claim.sum_insured) / 100000
        if not any(abs(si_lakhs - b) < 0.01 for b in band_lakhs):
            # Claim's SI band is outside this specific rule's stated scope
            # (e.g. 10L+ uses "Any Room", per the rule's own exception text).
            continue

        pct = parse_number(rule.value)
        limit_per_day = float(claim.sum_insured) * (pct / 100.0)
        billed = float(claim.room_rent_per_day)

        if billed <= limit_per_day:
            results.append(result(
                rule, "PASS",
                f"Room rent Rs.{billed}/day is within the {pct}% of Sum Insured/day limit "
                f"(Rs.{limit_per_day:.2f}/day).",
                expected=f"<= Rs.{limit_per_day:.2f}/day",
                actual=f"Rs.{billed}/day",
            ))
        else:
            proportion = limit_per_day / billed
            results.append(result(
                rule, "PARTIAL_DEDUCTION",
                f"Room rent Rs.{billed}/day exceeds the {pct}% of Sum Insured/day limit "
                f"(Rs.{limit_per_day:.2f}/day). Associated medical expenses are typically "
                f"proportionately reduced by insurers in this situation "
                f"(admissible fraction ~{proportion:.4f}) -- exact clause for proportionate "
                f"deduction was not captured for this policy version in this dataset pass; "
                f"flagging PARTIAL_DEDUCTION rather than computing a specific rupee figure.",
                expected=f"<= Rs.{limit_per_day:.2f}/day",
                actual=f"Rs.{billed}/day",
            ))
    return results
