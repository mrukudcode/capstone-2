"""
Hybrid Groq + deterministic financial validation engine.

Architecture:

1. Retrieve rules ONLY for the claim's policy version.
2. Ignore NEEDS_REVIEW rules.
3. Use Groq to:
   - determine whether a rule applies
   - compare claim data against the extracted rule
   - explain the finding
4. Use deterministic Python evaluators ONLY for exact financial calculations.
5. Avoid duplicate validation results:
   - Groq owns semantic validation.
   - Python financial evaluators calculate monetary consequences.
6. Preserve source provenance for every result.
7. Python determines the final application-level severity.
"""

from sqlalchemy.orm import Session

from app.models.models import (
    PolicyRule,
    Claim,
    ValidationRun,
    ValidationResult,
)

from app.rules.room_rent import evaluate_room_rent
from app.rules.sublimit import evaluate_sublimits
from app.rules.copay import evaluate_copay
from app.rules.deductible import evaluate_deductible

from app.services.financial_calculator import calculate_financials
from app.services.llm_claim_validator import validate_claim_against_rule


# ================================================================
# CLAIM -> DICTIONARY
# ================================================================

def claim_to_dict(claim: Claim):
    """
    Convert SQLAlchemy Claim object into a JSON-friendly dictionary
    that can safely be sent to Groq.

    Includes all claim fields relevant to:
        - PED / waiting periods
        - exclusions
        - policy continuity
        - hospitalization
        - preauthorization
        - claim deadlines
        - financial rules
        - injury / substance-related exclusions
        - medico-legal cases
        - maternity
        - procedures and diagnoses
    """

    return {
        # --------------------------------------------------------
        # BASIC CLAIM / POLICY IDENTIFICATION
        # --------------------------------------------------------

        "claim_ref": claim.claim_ref,
        "policy_version_db_id": claim.policy_version_db_id,

        "policy_start_date": claim.policy_start_date,
        "policy_end_date": claim.policy_end_date,

        "patient_ref": claim.patient_ref,
        "date_of_birth": claim.date_of_birth,
        "gender": claim.gender,

        # --------------------------------------------------------
        # HOSPITAL
        # --------------------------------------------------------

        "hospital_id": claim.hospital_id,
        "hospital_type": claim.hospital_type,
        "hospital_registration_number": claim.hospital_registration_number,
        "ip_registration_number": claim.ip_registration_number,

        # --------------------------------------------------------
        # ADMISSION / DISCHARGE
        # --------------------------------------------------------

        "admission_type": claim.admission_type,

        "admission_date": claim.admission_date,
        "admission_time": claim.admission_time,

        "discharge_date": claim.discharge_date,
        "discharge_time": claim.discharge_time,
        "discharge_status": claim.discharge_status,

        # --------------------------------------------------------
        # PROCEDURE
        # --------------------------------------------------------

        "procedure_description": claim.procedure_description,
        "procedure_code": claim.procedure_code,

        "procedure_2_description": claim.procedure_2_description,
        "procedure_2_code": claim.procedure_2_code,

        "procedure_3_description": claim.procedure_3_description,
        "procedure_3_code": claim.procedure_3_code,

        # --------------------------------------------------------
        # DIAGNOSIS
        # --------------------------------------------------------

        "diagnosis_code": claim.diagnosis_code,
        "diagnosis_description": claim.diagnosis_description,

        "additional_diagnoses": claim.additional_diagnoses,
        "comorbidities": claim.comorbidities,

        # --------------------------------------------------------
        # ROOM / FINANCIAL INFORMATION
        # --------------------------------------------------------

        "room_type": claim.room_type,
        "room_rent_per_day": claim.room_rent_per_day,

        "billed_amount": claim.billed_amount,

        "sum_insured": claim.sum_insured,
        "insured_age_at_entry": claim.insured_age_at_entry,

        "treatment_category": claim.treatment_category,
        "category_billed_amount": claim.category_billed_amount,

        "deductible_opted": claim.deductible_opted,
        "deductible_amount_opted": claim.deductible_amount_opted,

        # --------------------------------------------------------
        # PREAUTHORIZATION
        # --------------------------------------------------------

        "preauth_status": claim.preauth_status,
        "preauth_request_date": claim.preauth_request_date,
        "preauth_number": claim.preauth_number,
        "preauth_approval_date": claim.preauth_approval_date,

        # --------------------------------------------------------
        # CLAIM SUBMISSION / NOTIFICATION
        # --------------------------------------------------------

        "claim_type": claim.claim_type,

        "claim_filed_date": claim.claim_filed_date,
        "notification_date": claim.notification_date,

        # --------------------------------------------------------
        # POLICY CONTINUITY / PREVIOUS INSURER
        #
        # These are particularly important for:
        # PED waiting periods
        # continuity benefits
        # portability
        # policy-version rules
        # --------------------------------------------------------

        "previous_insurer_name": claim.previous_insurer_name,

        "previous_policy_start_date": claim.previous_policy_start_date,
        "previous_policy_end_date": claim.previous_policy_end_date,

        "continuous_coverage_since": claim.continuous_coverage_since,

        # --------------------------------------------------------
        # INJURY / SELF-INFLICTED / SUBSTANCE RELATED
        #
        # Used by exclusion rules.
        # --------------------------------------------------------

        "injury_related": claim.injury_related,
        "self_inflicted_injury": claim.self_inflicted_injury,

        "substance_abuse_related": claim.substance_abuse_related,
        "substance_abuse_test_done": claim.substance_abuse_test_done,

        # --------------------------------------------------------
        # MEDICO-LEGAL
        # --------------------------------------------------------

        "medico_legal_case": claim.medico_legal_case,
        "police_reported": claim.police_reported,
        "fir_number": claim.fir_number,

        # --------------------------------------------------------
        # MATERNITY
        # --------------------------------------------------------

        "delivery_date": claim.delivery_date,
        "gravida_status": claim.gravida_status,

        # --------------------------------------------------------
        # DOCUMENTS
        # --------------------------------------------------------
	"documents_submitted": claim.documents_submitted,
	"policy_document_received_date": claim.policy_document_received_date,
	"additional_clinical_details": claim.additional_clinical_details,

        # --------------------------------------------------------
        # POLICY CANCELLATION
        # --------------------------------------------------------

        "policy_cancelled_date": claim.policy_cancelled_date,

        # --------------------------------------------------------
        # PROVENANCE
        # --------------------------------------------------------

        "claim_provenance": claim.claim_provenance,
    }


# ================================================================
# POLICY RULE -> DICTIONARY
# ================================================================

def rule_to_dict(rule: PolicyRule):
    """
    Convert PolicyRule ORM object into a dictionary for Groq.
    """

    return {
        "candidate_id": rule.candidate_id,

        "rule_type": rule.rule_type,
        "rule_name": rule.rule_name,

        "condition": rule.condition,
        "value": rule.value,
        "unit": rule.unit,

        "applies_to": rule.applies_to,
        "exception": rule.exception,

        "source_document": rule.source_document,
        "source_page": rule.source_page,
        "source_section": rule.source_section,

        "source_text": rule.source_text,

        "extraction_method": rule.extraction_method,
        "confidence": rule.confidence,

        "review_status": rule.review_status,
        "provenance": rule.provenance,
    }


# ================================================================
# LLM FINDING -> APPLICATION SEVERITY
# ================================================================

def llm_finding_to_severity(llm_result):
    """
    Groq identifies the semantic finding.

    Python converts that finding into the application's severity.

    Groq NEVER directly decides the final application status or payout.
    """

    finding = str(
        llm_result.get("finding", "INSUFFICIENT_DATA")
    ).upper()

    applicable = llm_result.get(
        "applicable",
        False
    )

    # ------------------------------------------------------------
    # Rule does not apply.
    # ------------------------------------------------------------

    if not applicable:

        if finding == "NOT_APPLICABLE":
            return None

        return None

    # ------------------------------------------------------------
    # Explicit PASS
    # ------------------------------------------------------------

    if finding == "PASS":
        return "PASS"

    # ------------------------------------------------------------
    # Explicit policy violations
    # ------------------------------------------------------------

    if finding in (
        "FAIL",
        "LIMIT_EXCEEDED",
        "WAITING_PERIOD_NOT_MET",
        "ELIGIBILITY_VIOLATION",
    ):
        return "FAIL"

    # ------------------------------------------------------------
    # Rules requiring human review
    # ------------------------------------------------------------

    if finding in (
        "EXCLUSION_MATCH",
        "REQUIREMENT_MISSING",
        "DEADLINE_EXCEEDED",
        "PREAUTH_REQUIREMENT_NOT_MET",
        "INSUFFICIENT_DATA",
        "AMBIGUOUS",
    ):
        return "WARNING"

    # ------------------------------------------------------------
    # Conservative fallback.
    # ------------------------------------------------------------

    return "WARNING"


# ================================================================
# GROQ RULE VALIDATION
# ================================================================

def evaluate_rules_with_llm(
    active_rules,
    claim,
):
    """
    Send every active extracted rule to Groq.

    Groq decides:

        1. Does this rule apply?
        2. Does the claim satisfy it?
        3. What is the finding?
        4. Why?

    Python then converts the result into application severity.
    """

    results = []

    # ------------------------------------------------------------
    # Convert claim ONCE.
    # ------------------------------------------------------------

    claim_data = claim_to_dict(claim)

    # ------------------------------------------------------------
    # Validate every active rule.
    # ------------------------------------------------------------

    for rule in active_rules:

        rule_data = rule_to_dict(rule)

        try:

            llm_result = validate_claim_against_rule(
                claim_data=claim_data,
                rule=rule_data,
                source_text=rule.source_text or "",
            )

        except Exception as e:

            # ----------------------------------------------------
            # One failed Groq call must NOT stop the entire
            # validation process.
            # ----------------------------------------------------

            results.append({

                "rule_id": rule.candidate_id,

                "category": rule.rule_type,

                "severity": "WARNING",

                "reason": (
                    "Groq validation failed for this rule. "
                    "Manual review is required. "
                    f"Error: {str(e)}"
                ),

                "expected": (
                    rule.condition
                    or rule.value
                    or ""
                ),

                "actual": "LLM_VALIDATION_FAILED",

                "source_document": rule.source_document,
                "source_page": rule.source_page,
                "source_section": rule.source_section,

                "provenance": (
                    "LLM_VALIDATION_GROQ_FAILED | "
                    + str(rule.provenance or "")
                ),
            })

            continue

        # --------------------------------------------------------
        # Rule does not apply to this claim.
        #
        # Do NOT show NOT_APPLICABLE rules in the results.
        # --------------------------------------------------------

        if not llm_result.get(
            "applicable",
            False
        ):
            continue

        # --------------------------------------------------------
        # Convert LLM finding to application severity.
        # --------------------------------------------------------

        severity = llm_finding_to_severity(
            llm_result
        )

        if severity is None:
            continue

        # --------------------------------------------------------
        # Confidence
        # --------------------------------------------------------

        confidence = llm_result.get(
            "confidence",
            0
        )

        try:

            confidence = float(
                confidence
            )

        except (
            TypeError,
            ValueError
        ):

            confidence = 0.0

        confidence = max(
            0.0,
            min(
                1.0,
                confidence
            )
        )

        # --------------------------------------------------------
        # Explanation
        # --------------------------------------------------------

        reason = llm_result.get(
            "reason",
            "Groq evaluated the claim against the extracted policy rule."
        )

        reason = (
            f"{reason} "
            f"[Groq confidence: {confidence:.2f}]"
        )

        # --------------------------------------------------------
        # Result
        # --------------------------------------------------------

        results.append({

            "rule_id": rule.candidate_id,

            "category": rule.rule_type,

            "severity": severity,

            "reason": reason,

            "expected": llm_result.get(
                "expected",
                rule.condition
                or rule.value
                or ""
            ),

            "actual": llm_result.get(
                "actual",
                ""
            ),

            "source_document": rule.source_document,
            "source_page": rule.source_page,
            "source_section": rule.source_section,

            "provenance": (
                "LLM_VALIDATION_GROQ | "
                + str(rule.provenance or "")
            ),
        })

    return results


# ================================================================
# MAIN VALIDATION ENGINE
# ================================================================

def validate_claim(
    db: Session,
    claim: Claim,
):
    """
    Main hybrid validation function.

    Groq:
        - semantic rule applicability
        - semantic claim-vs-rule validation
        - explanation

    Python:
        - exact monetary calculations
        - financial consequences
        - final overall status
    """

    # ============================================================
    # 1. LOAD RULES FOR THIS POLICY VERSION ONLY
    # ============================================================

    all_rules = (
        db.query(PolicyRule)
        .filter(
            PolicyRule.policy_version_db_id
            == claim.policy_version_db_id
        )
        .all()
    )

    # ============================================================
    # 2. SEPARATE ACTIVE AND NEEDS_REVIEW RULES
    # ============================================================

    active_rules = [
        rule
        for rule in all_rules
        if rule.review_status in (
            "PENDING",
            "APPROVED",
        )
    ]

    needs_review_rules = [
        rule
        for rule in all_rules
        if rule.review_status == "NEEDS_REVIEW"
    ]

    results = []

    # ============================================================
    # 3. GROQ VALIDATES CLAIM AGAINST EXTRACTED RULES
    # ============================================================

    llm_results = evaluate_rules_with_llm(
        active_rules=active_rules,
        claim=claim,
    )

    results.extend(
        llm_results
    )

    # ============================================================
    # 4. DETERMINISTIC FINANCIAL CALCULATIONS ONLY
    #
    # IMPORTANT:
    #
    # These functions are NOT used to independently decide
    # semantic applicability.
    #
    # They calculate exact financial consequences only.
    # ============================================================

    room_rent_results = evaluate_room_rent(
        active_rules,
        claim,
    )

    sublimit_results = evaluate_sublimits(
        active_rules,
        claim,
    )

    copay_results = evaluate_copay(
        active_rules,
        claim,
    )

    deductible_results = evaluate_deductible(
        active_rules,
        claim,
    )

    # ============================================================
    # 5. FINANCIAL CALCULATION
    # ============================================================

    financials = calculate_financials(
        billed_amount=claim.billed_amount,

        room_rent_adjustment_results=room_rent_results,

        sublimit_results=sublimit_results,

        deductible_results=deductible_results,

        copay_results=copay_results,
    )

    # ============================================================
    # 6. DO NOT ADD DETERMINISTIC RESULTS TO `results`
    #
    # Groq owns semantic validation.
    # Python owns financial calculation.
    #
    # This prevents duplicate results such as:
    #
    # Groq -> PASS
    # Python -> PASS
    #
    # for the same rule.
    # ============================================================

    # ============================================================
    # 7. ADD NEEDS_REVIEW RULES
    # ============================================================

    for rule in needs_review_rules:

        results.append({

            "rule_id": rule.candidate_id,

            "category": rule.rule_type,

            "severity": "WARNING",

            "reason": (
                f"Policy rule {rule.candidate_id} is marked "
                "NEEDS_REVIEW and was not automatically evaluated."
            ),

            "expected": (
                "Manual review of source document is required "
                "before this rule can be trusted."
            ),

            "actual": "NOT_EVALUATED",

            "source_document": rule.source_document,
            "source_page": rule.source_page,
            "source_section": rule.source_section,

            "provenance": (
                "NEEDS_REVIEW | "
                + str(rule.provenance or "")
            ),
        })

    # ============================================================
    # 8. CREATE VALIDATION RUN
    # ============================================================

    run = ValidationRun(
        claim_id=claim.id
    )

    db.add(run)

    db.flush()

    # ============================================================
    # 9. DETERMINE OVERALL RESULT
    # ============================================================

    has_fail = any(
        result["severity"] == "FAIL"
        for result in results
    )

    has_warning = any(
        result["severity"] == "WARNING"
        for result in results
    )

    has_unresolved_rules = (
        len(needs_review_rules) > 0
    )

    # ------------------------------------------------------------
    # Priority:
    #
    # FAIL
    #   ↓
    # HUMAN_REVIEW_NEEDED
    #   ↓
    # SUBMISSION_READY
    # ------------------------------------------------------------

    if has_fail:

        overall = "FIX_BEFORE_SUBMISSION"

    elif (
        has_warning
        or has_unresolved_rules
    ):

        overall = "HUMAN_REVIEW_NEEDED"

    else:

        overall = "SUBMISSION_READY"

    run.overall_result = overall

    # ============================================================
    # 10. SAVE VALIDATION RESULTS
    # ============================================================

    for result in results:

        db.add(
            ValidationResult(

                claim_id=claim.id,

                validation_run_id=run.id,

                rule_id=result["rule_id"],

                category=result["category"],

                severity=result["severity"],

                reason=result["reason"],

                expected=result["expected"],

                actual=result["actual"],

                source_document=result[
                    "source_document"
                ],

                source_page=result[
                    "source_page"
                ],

                source_section=result[
                    "source_section"
                ],

                provenance=result[
                    "provenance"
                ],
            )
        )

    # ============================================================
    # 11. COMMIT
    # ============================================================

    db.commit()

    return (
        run,
        results,
        financials,
    )