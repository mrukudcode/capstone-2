"""
Rule engine orchestrator. Loads rules ONLY for claim.policy_version_id
(never across policy versions) and dispatches to per-category
deterministic evaluators. No LLM calls anywhere in this module or the
evaluators it calls.

Ambiguous/conflicting rules (review_status=NEEDS_REVIEW) are deliberately
excluded from automatic evaluation -- see the NEEDS_REVIEW handling below,
which surfaces their existence as a HUMAN_REVIEW_NEEDED signal without
silently activating them.
"""
from sqlalchemy.orm import Session
from app.models.models import PolicyRule, Claim, ValidationRun, ValidationResult
from app.rules.waiting_period import evaluate_waiting_periods
from app.rules.exclusion import evaluate_exclusions
from app.rules.room_rent import evaluate_room_rent
from app.rules.sublimit import evaluate_sublimits
from app.rules.copay import evaluate_copay
from app.rules.deductible import evaluate_deductible
from app.rules.deadline import evaluate_deadlines
from app.rules.preauth import evaluate_preauth
from app.rules.documentation import evaluate_documentation
from app.rules.eligibility import evaluate_eligibility
from app.rules.policy_status import evaluate_policy_status
from app.services.financial_calculator import calculate_financials


def validate_claim(db: Session, claim: Claim):
    all_rules = (
        db.query(PolicyRule)
        .filter(PolicyRule.policy_version_db_id == claim.policy_version_db_id)
        .all()
    )
    active_rules = [r for r in all_rules if r.review_status in ("PENDING", "APPROVED")]
    needs_review_rules = [r for r in all_rules if r.review_status == "NEEDS_REVIEW"]

    results = []
    results += evaluate_waiting_periods(active_rules, claim.policy_start_date, claim.admission_date)
    results += evaluate_exclusions(active_rules, claim.diagnosis_description)
    room_rent_results = evaluate_room_rent(active_rules, claim)
    results += room_rent_results
    sublimit_results = evaluate_sublimits(active_rules, claim)
    results += sublimit_results
    copay_results = evaluate_copay(active_rules, claim)
    results += copay_results
    deductible_results = evaluate_deductible(active_rules, claim)
    results += deductible_results
    results += evaluate_deadlines(active_rules, claim)
    results += evaluate_preauth(active_rules, claim)
    results += evaluate_documentation(active_rules, claim)
    results += evaluate_eligibility(active_rules, claim)
    results += evaluate_policy_status(active_rules, claim)

    for r in needs_review_rules:
        results.append({
            "rule_id": r.candidate_id,
            "category": r.rule_type,
            "severity": "WARNING",
            "reason": (
                f"This policy version has an unresolved rule ({r.candidate_id}, "
                f"{r.rule_type}) flagged review_status=NEEDS_REVIEW and was NOT "
                f"automatically evaluated. See docs/HDFC_ERGO_UIN_REVIEW.md."
            ),
            "expected": "Manual review of source before this rule can be trusted",
            "actual": "NOT_EVALUATED",
            "source_document": r.source_document,
            "source_page": r.source_page,
            "source_section": r.source_section,
            "provenance": r.provenance,
        })

    financials = calculate_financials(
        billed_amount=claim.billed_amount,
        room_rent_adjustment_results=room_rent_results,
        sublimit_results=sublimit_results,
        deductible_results=deductible_results,
        copay_results=copay_results,
    )

    run = ValidationRun(claim_id=claim.id)
    db.add(run)
    db.flush()

    has_fail = any(r["severity"] == "FAIL" for r in results)
    has_unresolved = len(needs_review_rules) > 0
    has_warning = any(r["severity"] == "WARNING" for r in results)

    if has_fail:
        overall = "FIX_BEFORE_SUBMISSION"
    elif has_unresolved or has_warning:
        overall = "HUMAN_REVIEW_NEEDED"
    else:
        overall = "SUBMISSION_READY"
    run.overall_result = overall

    for r in results:
        db.add(ValidationResult(
            claim_id=claim.id,
            validation_run_id=run.id,
            rule_id=r["rule_id"],
            category=r["category"],
            severity=r["severity"],
            reason=r["reason"],
            expected=r["expected"],
            actual=r["actual"],
            source_document=r["source_document"],
            source_page=r["source_page"],
            source_section=r["source_section"],
            provenance=r["provenance"],
        ))
    db.commit()
    return run, results, financials
