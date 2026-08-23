"""Shared deterministic parsing helpers. No LLM calls anywhere in this file."""
import re


def parse_number(value: str):
    """Extract the first plain number from a rule's value field, or None."""
    m = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    return float(m.group(1)) if m else None


def parse_days(value: str, unit: str):
    unit = (unit or "").upper()
    n = parse_number(value)
    if n is None:
        return None
    if unit == "DAYS":
        return n
    if unit == "HOURS":
        return n / 24.0
    if unit == "MONTHS":
        return n * 30
    if unit == "YEARS":
        return n * 365
    return None


def parse_hours(value: str, unit: str):
    unit = (unit or "").upper()
    n = parse_number(value)
    if n is None:
        return None
    if unit == "HOURS":
        return n
    if unit == "DAYS":
        return n * 24
    return None


def result(rule, severity, reason, expected, actual):
    return {
        "rule_id": rule.candidate_id,
        "category": rule.rule_type,
        "severity": severity,
        "reason": reason,
        "expected": expected,
        "actual": actual,
        "source_document": rule.source_document,
        "source_page": rule.source_page,
        "source_section": rule.source_section,
        "provenance": rule.provenance,
    }
