"""
EXCLUSION and NON_COVERED_TREATMENT evaluator.

These rules in the actual dataset are qualitative (a named condition or
treatment type is excluded), not numeric thresholds -- e.g. SA26-015
"Refractive error less than 7.5 dioptres". Deterministic evaluation here
means keyword matching against the claim's diagnosis/procedure text, NOT
any LLM semantic judgement. This is intentionally conservative: it only
flags a rule when a keyword drawn directly from the rule's own condition/
rule_name text appears in the claim's diagnosis_description, and always
surfaces the match as WARNING (never an automatic FAIL) because free-text
keyword matching cannot reliably confirm clinical applicability -- e.g.
matching "cosmetic" doesn't establish whether a specific procedure is
reconstructive (covered) or purely cosmetic (excluded); a human must
confirm using the cited source text.
"""
import re
from app.rules.common import result

# Rule value/condition fields for exclusions are often NOT_APPLICABLE; the
# actual matchable text lives in rule_name/condition. Extract simple
# lowercase keywords (>=4 chars) to check against diagnosis text.
_STOPWORDS = {
    "the", "and", "for", "any", "not", "with", "this", "that", "from",
    "less", "than", "shall", "exclusion", "expenses", "related", "treatment",
}


def _keywords(text):
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def evaluate_exclusions(rules, diagnosis_description: str):
    if not diagnosis_description:
        return []
    diag = diagnosis_description.lower()
    results = []
    for rule in rules:
        if rule.rule_type not in ("EXCLUSION", "NON_COVERED_TREATMENT"):
            continue
        kws = _keywords(rule.rule_name) | _keywords(rule.condition)
        matched = {kw for kw in kws if kw in diag}
        if matched:
            results.append(result(
                rule, "WARNING",
                f"Diagnosis/treatment text contains term(s) {sorted(matched)} that overlap "
                f"with an exclusion rule's own description. Keyword overlap does NOT "
                f"confirm applicability -- human review required against the cited source text.",
                expected=f"Not matching exclusion: {rule.rule_name}",
                actual=diagnosis_description,
            ))
    return results
