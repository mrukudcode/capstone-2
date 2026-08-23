"""
Deterministic waiting-period evaluation. No LLM involved in PASS/FAIL decisions.

Evaluates INITIAL_WAITING_PERIOD, PED_WAITING_PERIOD, and
SPECIFIED_DISEASE_WAITING_PERIOD rule types against a claim's elapsed policy
period (admission_date - policy_start_date), using ONLY the rules stored for
claim.policy_version_id (never across policy versions).
"""
from datetime import date
import re


def _parse_days(value: str, unit: str) -> int:
    """Convert a rule's (value, unit) into an equivalent day count for comparison."""
    unit = (unit or "").upper()
    # value can be a single number ("30", "24") or a range ("30 to 60") -- for
    # waiting periods we only expect single numbers; ranges belong to other
    # rule types (e.g. portability lead time) and are not evaluated here.
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*$", str(value))
    if not m:
        raise ValueError(f"Cannot parse waiting-period value: {value!r}")
    n = float(m.group(1))
    if unit == "DAYS":
        return int(n)
    if unit == "MONTHS":
        return int(round(n * 30))  # approximation, documented
    if unit == "YEARS":
        return int(round(n * 365))
    raise ValueError(f"Unsupported waiting-period unit: {unit!r}")


def evaluate_waiting_periods(rules, policy_start_date: date, admission_date: date):
    """
    rules: iterable of PolicyRule ORM objects, already filtered to a single
           policy_version_id by the caller (engine.py) -- this function does
           not itself filter by policy version, to keep it a pure function.
    Returns a list of result dicts (rule_id, category, severity, reason,
    expected, actual, source_document, source_page, source_section, provenance).
    """
    elapsed_days = (admission_date - policy_start_date).days
    results = []

    for rule in rules:
        if rule.rule_type not in (
            "INITIAL_WAITING_PERIOD",
            "PED_WAITING_PERIOD",
            "SPECIFIED_DISEASE_WAITING_PERIOD",
        ):
            continue
        try:
            required_days = _parse_days(rule.value, rule.unit)
        except ValueError:
            # Rule value not machine-parseable (e.g. multi-part condition) --
            # deterministic engine cannot safely evaluate it automatically.
            results.append({
                "rule_id": rule.candidate_id,
                "category": rule.rule_type,
                "severity": "WARNING",
                "reason": f"Rule value '{rule.value} {rule.unit}' could not be parsed by the "
                          f"deterministic engine; flag for human review rather than guess.",
                "expected": f"{rule.value} {rule.unit}",
                "actual": f"{elapsed_days} days elapsed",
                "source_document": rule.source_document,
                "source_page": rule.source_page,
                "source_section": rule.source_section,
                "provenance": rule.provenance,
            })
            continue

        passed = elapsed_days >= required_days
        results.append({
            "rule_id": rule.candidate_id,
            "category": rule.rule_type,
            "severity": "PASS" if passed else "FAIL",
            "reason": (
                f"Elapsed policy period ({elapsed_days} days) satisfies the "
                f"{rule.value} {rule.unit} waiting period."
                if passed else
                f"Elapsed policy period ({elapsed_days} days) is short of the "
                f"required {rule.value} {rule.unit} ({required_days} days) waiting period."
            ),
            "expected": f">= {required_days} days ({rule.value} {rule.unit})",
            "actual": f"{elapsed_days} days",
            "source_document": rule.source_document,
            "source_page": rule.source_page,
            "source_section": rule.source_section,
            "provenance": rule.provenance,
        })
    return results
