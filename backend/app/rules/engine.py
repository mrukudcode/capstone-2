"""
Hybrid Groq + deterministic validation engine.

Architecture
------------

1. Retrieve rules ONLY for the claim's policy version.
2. Separate APPROVED/PENDING rules from NEEDS_REVIEW rules.
3. Route rules using app.rules.llm_routing.
4. Use Groq only for genuinely semantic policy rules.
5. Use deterministic Python evaluators for:
      - room rent
      - sublimits
      - co-payment
      - deductible
      - claim filing deadlines
      - emergency notification deadlines
      - planned-hospitalization preauthorization
6. Python owns exact financial consequences.
7. NEEDS_REVIEW rules are surfaced as WARNING.
8. Every validation result preserves source provenance.
9. Python determines the final application-level result.

This system is a pre-submission validation assistant.

It is NOT:
    - an insurer approval predictor
    - an insurer rejection predictor
    - a guaranteed payout calculator
    - connected to NHCX
"""

from sqlalchemy.orm import Session

from app.models.models import (
    PolicyRule,
    Claim,
    ValidationRun,
    ValidationResult,
)

# ----------------------------------------------------------------
# DETERMINISTIC EVALUATORS
# ----------------------------------------------------------------

from app.rules.room_rent import evaluate_room_rent
from app.rules.sublimit import evaluate_sublimits
from app.rules.copay import evaluate_copay
from app.rules.deductible import evaluate_deductible
from app.rules.deadline import evaluate_deadlines
from app.rules.preauth import evaluate_preauth
import time

# ----------------------------------------------------------------
# RULE ROUTING
# ----------------------------------------------------------------

from app.rules.llm_routing import should_use_llm

# ----------------------------------------------------------------
# FINANCIAL CALCULATION
# ----------------------------------------------------------------

from app.services.financial_calculator import calculate_financials

# ----------------------------------------------------------------
# GROQ
# ----------------------------------------------------------------

from app.services.llm_claim_validator import validate_claim_against_rule


# ================================================================
# CLAIM -> DICTIONARY
# ================================================================

def claim_to_dict(claim: Claim):
    """
    Convert SQLAlchemy Claim object into a JSON-friendly dictionary.
    """

    return {
        # CLAIM / POLICY
        "claim_ref": claim.claim_ref,
        "policy_version_db_id": claim.policy_version_db_id,
        "policy_start_date": claim.policy_start_date,
        "policy_end_date": claim.policy_end_date,
        "policy_cancelled_date": claim.policy_cancelled_date,
        "sum_insured": claim.sum_insured,
        "insured_age_at_entry": claim.insured_age_at_entry,

        # PREVIOUS INSURANCE / CONTINUITY
        "previous_insurer_name": claim.previous_insurer_name,
        "previous_policy_start_date": claim.previous_policy_start_date,
        "previous_policy_end_date": claim.previous_policy_end_date,
        "continuous_coverage_since": claim.continuous_coverage_since,

        # PATIENT
        "patient_ref": claim.patient_ref,
        "date_of_birth": claim.date_of_birth,
        "gender": claim.gender,

        # HOSPITAL
        "hospital_id": claim.hospital_id,
        "hospital_type": claim.hospital_type,
        "hospital_registration_number": claim.hospital_registration_number,
        "ip_registration_number": claim.ip_registration_number,

        # HOSPITALISATION
        "admission_date": claim.admission_date,
        "admission_time": claim.admission_time,
        "discharge_date": claim.discharge_date,
        "discharge_time": claim.discharge_time,
        "admission_type": claim.admission_type,
        "claim_type": claim.claim_type,
        "discharge_status": claim.discharge_status,

        # DIAGNOSIS
        "diagnosis_code": claim.diagnosis_code,
        "diagnosis_description": claim.diagnosis_description,
        "additional_diagnoses": claim.additional_diagnoses,
        "comorbidities": claim.comorbidities,

        # PROCEDURES
        "procedure_description": claim.procedure_description,
        "procedure_code": claim.procedure_code,
        "procedure_2_description": claim.procedure_2_description,
        "procedure_2_code": claim.procedure_2_code,
        "procedure_3_description": claim.procedure_3_description,
        "procedure_3_code": claim.procedure_3_code,

        # ROOM / BILLING
        "room_type": claim.room_type,
        "room_rent_per_day": claim.room_rent_per_day,
        "billed_amount": claim.billed_amount,

        # TREATMENT
        "treatment_category": claim.treatment_category,
        "category_billed_amount": claim.category_billed_amount,

        # PREAUTHORIZATION
        "preauth_status": claim.preauth_status,
        "preauth_number": claim.preauth_number,
        "preauth_request_date": claim.preauth_request_date,
        "preauth_approval_date": claim.preauth_approval_date,

        # CLAIM NOTIFICATION / SUBMISSION
        "notification_date": claim.notification_date,
        "claim_filed_date": claim.claim_filed_date,

        # INJURY / EXCLUSION
        "injury_related": claim.injury_related,
        "self_inflicted_injury": claim.self_inflicted_injury,
        "substance_abuse_related": claim.substance_abuse_related,
        "substance_abuse_test_done": claim.substance_abuse_test_done,

        # MEDICO-LEGAL
        "medico_legal_case": claim.medico_legal_case,
        "police_reported": claim.police_reported,
        "fir_number": claim.fir_number,

        # MATERNITY
        "delivery_date": claim.delivery_date,
        "gravida_status": claim.gravida_status,

        # DEDUCTIBLE
        "deductible_opted": claim.deductible_opted,
        "deductible_amount_opted": claim.deductible_amount_opted,

        # DOCUMENTS
        "documents_submitted": claim.documents_submitted,

        # PROVENANCE
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
    Convert Groq's finding into application severity.

    Groq does NOT determine the final application result.
    """

    if not isinstance(llm_result, dict):
        return "WARNING"

    finding = str(
        llm_result.get(
            "finding",
            "INSUFFICIENT_DATA"
        )
    ).strip().upper()

    applicable = llm_result.get(
        "applicable",
        False
    )

    # ------------------------------------------------------------
    # NOT APPLICABLE
    # ------------------------------------------------------------

    if finding == "NOT_APPLICABLE":
        return None

    if not applicable:
        return None

    # ------------------------------------------------------------
    # PASS
    # ------------------------------------------------------------

    if finding == "PASS":
        return "PASS"

    # ------------------------------------------------------------
    # FAIL
    # ------------------------------------------------------------

    if finding == "FAIL":
        return "FAIL"

    # ------------------------------------------------------------
    # INSUFFICIENT_DATA / anything uncertain
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
    Evaluate only rules configured for LLM semantic validation.

    Routing is controlled centrally by should_use_llm().

    Deterministic rules such as:
        - ROOM_RENT
        - SUBLIMIT
        - COPAY
        - DEDUCTIBLE
        - CLAIM_FILING_DEADLINE
        - CLAIM_NOTIFICATION_DEADLINE
        - PREAUTH_REQUIREMENT

    are NOT sent to Groq.
    """

    results = []

    claim_data = claim_to_dict(claim)

    for rule in active_rules:

        rule_type = str(
            rule.rule_type or ""
        ).strip().upper()

        # --------------------------------------------------------
        # CENTRALIZED ROUTING
        # --------------------------------------------------------

        if not should_use_llm(rule_type):
            continue

        rule_data = rule_to_dict(rule)

        # --------------------------------------------------------
        # CALL GROQ
        # --------------------------------------------------------

        try:
	    #time.sleep(2)
            llm_result = validate_claim_against_rule(
                claim_data=claim_data,
                rule=rule_data,
                source_text=rule.source_text or "",
            )

        except Exception as e:

            # ----------------------------------------------------
            # Do not expose huge Groq errors.
            # ----------------------------------------------------

            error_text = str(e)

            # Detect Groq rate-limit errors.
            is_rate_limit = (
                "429" in error_text
                or "rate_limit" in error_text.lower()
                or "rate limit" in error_text.lower()
            )

            if is_rate_limit:
                error_message = (
                    "Groq rate limit reached while validating "
                    "this policy rule."
                )
            else:
                error_message = (
                    "Groq validation failed."
                )

            results.append({
                "rule_id": rule.candidate_id,
                "category": rule.rule_type,
                "severity": "WARNING",

                "reason": (
                    error_message
                    + " Manual review is required."
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
        # RESPONSE VALIDATION
        # --------------------------------------------------------

        if not isinstance(llm_result, dict):

            results.append({
                "rule_id": rule.candidate_id,
                "category": rule.rule_type,
                "severity": "WARNING",

                "reason": (
                    "Groq returned an invalid response for this "
                    "rule. Manual review is required."
                ),

                "expected": (
                    rule.condition
                    or rule.value
                    or ""
                ),

                "actual": "INVALID_LLM_RESPONSE",

                "source_document": rule.source_document,
                "source_page": rule.source_page,
                "source_section": rule.source_section,

                "provenance": (
                    "LLM_VALIDATION_INVALID_RESPONSE | "
                    + str(rule.provenance or "")
                ),
            })

            continue

        # --------------------------------------------------------
        # DETERMINE SEVERITY
        # --------------------------------------------------------

        severity = llm_finding_to_severity(
            llm_result
        )

        # NOT_APPLICABLE -> don't show as a validation issue.
        if severity is None:
            continue

        # --------------------------------------------------------
        # CONFIDENCE
        # --------------------------------------------------------

        confidence = llm_result.get(
            "confidence",
            0
        )

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(
            0.0,
            min(1.0, confidence)
        )

        # --------------------------------------------------------
        # REASON
        # --------------------------------------------------------

        reason = llm_result.get(
            "reason",
            "Groq evaluated the claim against the extracted policy rule."
        )

        if not isinstance(reason, str):
            reason = str(reason)

        reason = (
            f"{reason} "
            f"[Groq confidence: {confidence:.2f}]"
        )

        # --------------------------------------------------------
        # EXPECTED / ACTUAL
        # --------------------------------------------------------

        expected = llm_result.get(
            "expected",
            rule.condition
            or rule.value
            or ""
        )

        actual = llm_result.get(
            "actual",
            ""
        )

        # --------------------------------------------------------
        # STORE
        # --------------------------------------------------------

        results.append({
            "rule_id": rule.candidate_id,
            "category": rule.rule_type,
            "severity": severity,

            "reason": reason,

            "expected": str(expected),
            "actual": str(actual),

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
# DETERMINISTIC RESULT -> VALIDATION RESULT
# ================================================================

def _deterministic_result_to_validation_result(
    result,
    category,
):
    """
    Convert deterministic evaluator output into common format.
    """

    if not isinstance(result, dict):
        return None

    rule_id = result.get(
        "rule_id",
        result.get("candidate_id")
    )

    if not rule_id:
        return None

    status = str(
        result.get(
            "status",
            result.get(
                "severity",
                "WARNING"
            )
        )
    ).upper()

    # ------------------------------------------------------------
    # PASS
    # ------------------------------------------------------------

    if status in (
        "PASS",
        "WITHIN_LIMIT",
        "NO_ADJUSTMENT",
    ):
        severity = "PASS"

    # ------------------------------------------------------------
    # Violations remain WARNING.
    #
    # This is intentional for:
    #   - late claim filing
    #   - late notification
    #   - insufficient preauth lead time
    #
    # They require human/insurer review rather than automatic
    # claim rejection.
    # ------------------------------------------------------------

    elif status in (
        "FAIL",
        "LIMIT_EXCEEDED",
        "DEDUCTION_APPLIED",
        "DEADLINE_EXCEEDED",
        "PREAUTH_REQUIREMENT_NOT_MET",
    ):
        severity = "WARNING"

    else:
        severity = "WARNING"

    reason = result.get(
        "reason",
        result.get(
            "message",
            "Deterministic rule evaluated."
        )
    )

    return {
        "rule_id": rule_id,

        "category": category,

        "severity": severity,

        "reason": str(reason),

        "expected": str(
            result.get(
                "expected",
                ""
            )
        ),

        "actual": str(
            result.get(
                "actual",
                ""
            )
        ),

        "source_document": result.get(
            "source_document"
        ),

        "source_page": result.get(
            "source_page"
        ),

        "source_section": result.get(
            "source_section"
        ),

        "provenance": (
            "DETERMINISTIC_RULE_EVALUATION | "
            + str(
                result.get(
                    "provenance",
                    ""
                )
            )
        ),
    }


# ================================================================
# ADD DETERMINISTIC RESULTS
# ================================================================

def _add_deterministic_results(
    results,
    evaluator_results,
    category,
):
    """
    Add deterministic evaluator results.
    """

    if not evaluator_results:
        return

    if isinstance(evaluator_results, dict):
        evaluator_results = [
            evaluator_results
        ]

    if not isinstance(
        evaluator_results,
        (list, tuple)
    ):
        return

    for evaluator_result in evaluator_results:

        validation_result = (
            _deterministic_result_to_validation_result(
                evaluator_result,
                category,
            )
        )

        if validation_result:
            results.append(
                validation_result
            )


# ================================================================
# ADD FINANCIAL VALIDATION RESULTS
# ================================================================

def _add_financial_validation_results(
    results,
    room_rent_results,
    sublimit_results,
    copay_results,
    deductible_results,
):
    """
    Add deterministic financial findings.
    """

    evaluator_groups = [
        (
            room_rent_results,
            "ROOM_RENT"
        ),
        (
            sublimit_results,
            "SUBLIMIT"
        ),
        (
            copay_results,
            "COPAY"
        ),
        (
            deductible_results,
            "DEDUCTIBLE"
        ),
    ]

    for evaluator_results, category in evaluator_groups:

        if not evaluator_results:
            continue

        if isinstance(evaluator_results, dict):
            evaluator_results = [
                evaluator_results
            ]

        if not isinstance(
            evaluator_results,
            (list, tuple)
        ):
            continue

        for evaluator_result in evaluator_results:

            validation_result = (
                _deterministic_result_to_validation_result(
                    evaluator_result,
                    category,
                )
            )

            if validation_result:
                results.append(
                    validation_result
                )


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
        - deadline calculations
        - preauthorization calculations
        - final overall result
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
    # 2. SEPARATE ACTIVE / NEEDS_REVIEW
    # ============================================================

    active_rules = [
        rule
        for rule in all_rules
        if str(
            rule.review_status or ""
        ).upper()
        in (
            "PENDING",
            "APPROVED",
        )
    ]

    needs_review_rules = [
        rule
        for rule in all_rules
        if str(
            rule.review_status or ""
        ).upper()
        == "NEEDS_REVIEW"
    ]

    results = []

    # ============================================================
    # 3. GROQ SEMANTIC VALIDATION
    # ============================================================

    llm_results = evaluate_rules_with_llm(
        active_rules=active_rules,
        claim=claim,
    )

    results.extend(
        llm_results
    )

    # ============================================================
    # 4. DETERMINISTIC EVALUATION
    # ============================================================

    financial_evaluator_error = None

    room_rent_results = []
    sublimit_results = []
    copay_results = []
    deductible_results = []

    deadline_results = []
    preauth_results = []

    try:

        # --------------------------------------------------------
        # FINANCIAL
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # DEADLINES
        # --------------------------------------------------------

        deadline_results = evaluate_deadlines(
            active_rules,
            claim,
        )

        # --------------------------------------------------------
        # PREAUTHORIZATION
        # --------------------------------------------------------

        preauth_results = evaluate_preauth(
            active_rules,
            claim,
        )

        # --------------------------------------------------------
        # FINANCIAL CALCULATION
        # --------------------------------------------------------

        financials = calculate_financials(
            billed_amount=claim.billed_amount,

            room_rent_adjustment_results=
                room_rent_results,

            sublimit_results=
                sublimit_results,

            deductible_results=
                deductible_results,

            copay_results=
                copay_results,
        )

    except Exception as e:

        financial_evaluator_error = str(e)

        financials = {
            "status":
                "FINANCIAL_CALCULATION_FAILED",

            "error":
                str(e),
        }

    # ============================================================
    # 5. ADD FINANCIAL FINDINGS
    # ============================================================

    if not financial_evaluator_error:

        _add_financial_validation_results(
            results=results,

            room_rent_results=
                room_rent_results,

            sublimit_results=
                sublimit_results,

            copay_results=
                copay_results,

            deductible_results=
                deductible_results,
        )

    # ============================================================
    # 6. ADD DEADLINE FINDINGS
    # ============================================================

    _add_deterministic_results(
        results=results,

        evaluator_results=
            deadline_results,

        category=
            "CLAIM_DEADLINE",
    )

    # ============================================================
    # 7. ADD PREAUTH FINDINGS
    # ============================================================

    _add_deterministic_results(
        results=results,

        evaluator_results=
            preauth_results,

        category=
            "PREAUTH_REQUIREMENT",
    )

    # ============================================================
    # 8. FINANCIAL CALCULATION FAILURE
    # ============================================================

    if financial_evaluator_error:

        results.append({

            "rule_id":
                "FINANCIAL-CALCULATION",

            "category":
                "FINANCIAL",

            "severity":
                "WARNING",

            "reason":
                (
                    "Deterministic financial calculation failed. "
                    "Manual review is required before relying on "
                    "the financial estimate."
                ),

            "expected":
                "Successful deterministic calculation",

            "actual":
                "FINANCIAL_CALCULATION_FAILED",

            "source_document":
                None,

            "source_page":
                None,

            "source_section":
                None,

            "provenance":
                "DETERMINISTIC_FINANCIAL_CALCULATION_FAILED",
        })

    # ============================================================
    # 9. ADD NEEDS_REVIEW RULES
    # ============================================================

    for rule in needs_review_rules:

        results.append({

            "rule_id":
                rule.candidate_id,

            "category":
                rule.rule_type,

            "severity":
                "WARNING",

            "reason":
                (
                    f"Policy rule {rule.candidate_id} is marked "
                    "NEEDS_REVIEW and was not automatically "
                    "evaluated."
                ),

            "expected":
                (
                    "Manual review of source document is required "
                    "before this rule can be trusted."
                ),

            "actual":
                "NOT_EVALUATED",

            "source_document":
                rule.source_document,

            "source_page":
                rule.source_page,

            "source_section":
                rule.source_section,

            "provenance":
                (
                    "NEEDS_REVIEW | "
                    + str(rule.provenance or "")
                ),
        })

    # ============================================================
    # 10. CREATE VALIDATION RUN
    # ============================================================

    run = ValidationRun(
        claim_id=claim.id
    )

    db.add(run)

    db.flush()

    # ============================================================
    # 11. DETERMINE OVERALL RESULT
    # ============================================================

    has_fail = any(
        result.get("severity") == "FAIL"
        for result in results
    )

    has_warning = any(
        result.get("severity") == "WARNING"
        for result in results
    )

    if has_fail:

        overall = (
            "FIX_BEFORE_SUBMISSION"
        )

    elif has_warning:

        overall = (
            "HUMAN_REVIEW_NEEDED"
        )

    else:

        overall = (
            "SUBMISSION_READY"
        )

    run.overall_result = overall

    # ============================================================
    # 12. SAVE VALIDATION RESULTS
    # ============================================================

    for result in results:

        db.add(
            ValidationResult(

                claim_id=
                    claim.id,

                validation_run_id=
                    run.id,

                rule_id=
                    result["rule_id"],

                category=
                    result["category"],

                severity=
                    result["severity"],

                reason=
                    result["reason"],

                expected=
                    str(
                        result.get(
                            "expected",
                            ""
                        )
                    ),

                actual=
                    str(
                        result.get(
                            "actual",
                            ""
                        )
                    ),

                source_document=
                    result.get(
                        "source_document"
                    ),

                source_page=
                    result.get(
                        "source_page"
                    ),

                source_section=
                    result.get(
                        "source_section"
                    ),

                provenance=
                    result.get(
                        "provenance"
                    ),
            )
        )

    # ============================================================
    # 13. COMMIT
    # ============================================================

    db.commit()

    return (
        run,
        results,
        financials,
    )