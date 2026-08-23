"""
POLICY_INACTIVE and POLICY_EXPIRED evaluator.

HONEST LIMITATION: the extracted rules tagged POLICY_INACTIVE (HDFC21-009,
IRDAI-005) and POLICY_EXPIRED (IRDAI-010) describe ADMINISTRATIVE notice
periods and withdrawn-product renewal windows -- e.g. "policyholder must
give 7 days' written notice to cancel" -- not a directly-statable "coverage
ends on date X" rule. Citing those specific extracted rule rows as the
provenance for a claim-level "was this policy active on the admission
date" check would misattribute a business-logic inference to source text
that doesn't literally say that.

So this evaluator implements the check as clearly-labelled DERIVED
business logic (provenance="DERIVED_LOGIC_NOT_FROM_SOURCE_RULE"), only
when the claim itself supplies the relevant date fields, and does NOT
cite a specific candidate_id/source_document/source_page -- because none
of the extracted rows actually states this specific proposition.
"""
from app.rules.common import result


class _SyntheticRule:
    """Lightweight stand-in so result() can be reused for derived (non-extracted) checks."""
    def __init__(self, candidate_id, rule_type):
        self.candidate_id = candidate_id
        self.rule_type = rule_type
        self.source_document = "NOT_APPLICABLE_DERIVED_LOGIC"
        self.source_page = "NOT_APPLICABLE_DERIVED_LOGIC"
        self.source_section = "NOT_APPLICABLE_DERIVED_LOGIC"
        self.provenance = "DERIVED_LOGIC_NOT_FROM_SOURCE_RULE"


def evaluate_policy_status(rules, claim):
    results = []

    if claim.policy_cancelled_date is not None and claim.admission_date is not None:
        rule = _SyntheticRule("DERIVED-POLICY-INACTIVE", "POLICY_INACTIVE")
        if claim.admission_date >= claim.policy_cancelled_date:
            results.append(result(
                rule, "FAIL",
                f"Admission date ({claim.admission_date}) is on/after the policy's recorded "
                f"cancellation date ({claim.policy_cancelled_date}). This is a derived business-"
                f"logic check, not an extracted policy clause -- no source document states this "
                f"specific proposition verbatim in the current dataset.",
                expected=f"admission_date < {claim.policy_cancelled_date}",
                actual=str(claim.admission_date),
            ))
        else:
            results.append(result(
                rule, "PASS",
                f"Admission date ({claim.admission_date}) is before the policy's recorded "
                f"cancellation date ({claim.policy_cancelled_date}).",
                expected=f"admission_date < {claim.policy_cancelled_date}",
                actual=str(claim.admission_date),
            ))

    if claim.policy_end_date is not None and claim.admission_date is not None:
        rule = _SyntheticRule("DERIVED-POLICY-EXPIRED", "POLICY_EXPIRED")
        if claim.admission_date > claim.policy_end_date:
            results.append(result(
                rule, "FAIL",
                f"Admission date ({claim.admission_date}) is after the policy's end date "
                f"({claim.policy_end_date}). This is a derived business-logic check, not an "
                f"extracted policy clause -- see rule module docstring.",
                expected=f"admission_date <= {claim.policy_end_date}",
                actual=str(claim.admission_date),
            ))
        else:
            results.append(result(
                rule, "PASS",
                f"Admission date ({claim.admission_date}) is within the policy period "
                f"(ends {claim.policy_end_date}).",
                expected=f"admission_date <= {claim.policy_end_date}",
                actual=str(claim.admission_date),
            ))

    return results
