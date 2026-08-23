"""
ELIGIBILITY_FAILURE evaluator.

HONEST STATUS: the extracted dataset contains ZERO rule_type=ELIGIBILITY_FAILURE
rows (verified via scripts/validate_dataset.py rule_type breakdown as of this
session). No eligibility rules (e.g. minimum/maximum entry age, family
definition constraints) were extracted from the source documents in this
pass, even though such clauses likely exist in the full Policy Wording
PDFs (e.g. Star Assure's "Minimum - 91 days and Maximum upto 75 years"
seen in a search snippet but not yet ingested with a page citation).

This function therefore always returns an empty list -- it does not
fabricate an eligibility check from memory of typical Indian health
insurance entry-age rules. Extending this evaluator requires first adding
genuinely page-cited ELIGIBILITY_FAILURE rows to policy_rule_candidates.csv.
"""


def evaluate_eligibility(rules, claim):
    return []
