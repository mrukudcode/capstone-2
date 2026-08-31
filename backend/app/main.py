from dotenv import load_dotenv

load_dotenv()

"""
FastAPI application.

Two route sets are exposed and backed by the same handler functions:

    /api/*
        Legacy routes retained for compatibility.

    Root-level routes:
        /health
        /policies
        /claims
        /documents/...
        /rules/...
        /icd10/...

The application is an:

    Explainable Pre-Submission Health Insurance Claim Rule Validator.

IMPORTANT
---------

The claim workflow supports:

    1. Create claim
    2. Validate claim
    3. Identify missing / problematic information
    4. Update missing claim data
    5. Re-validate the SAME claim
    6. Preserve previous validation runs for audit/history

This system is NOT:

    - an insurer approval predictor
    - an insurer rejection predictor
    - a guaranteed payout calculator
    - connected to NHCX

Claims used for testing are synthetic records.
"""

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
import os
import hashlib
import re
import uuid

from app.database.db import get_db

from app.models.models import (
    PolicyVersion,
    PolicyRule,
    Claim,
    Policy,
    Insurer,
    Document,
    ValidationRun,
    ValidationResult,
)

from app.services.pdf_extractor import extract_text_with_pages
from app.services.policy_rule_extractor import extract_rules_from_text

from app.schemas.schemas import (
    ClaimCreate,
    ClaimUpdate,
    ValidationRunOut,
)

from app.rules.engine import validate_claim

from app.api.qa import router as qa_router
from app.api.icd10 import router as icd10_router


# ================================================================
# DATA ROOT
# ================================================================

_DATA_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "data",
    )
)


# ================================================================
# DOCUMENT -> EXTRACTED TEXT MAPPING
# ================================================================

_DOCUMENT_TEXT_FILES = {

    "STAR_ASSURE_2026_CIS":
        "raw/policies/star_health/"
        "star_assure_2026_CIS_extracted_text.txt",

    "HDFC_OPTIMA_SECURE_2026_POLICY_WORDING":
        "raw/policies/hdfc_ergo/"
        "hdfc_optima_secure_2026_policy_wording_extracted_text.txt",

    "HDFC_OPTIMA_SECURE_2026_CIS":
        "raw/policies/hdfc_ergo/"
        "hdfc_optima_secure_2026_CIS_extracted_text.txt",

    "HDFC_OPTIMA_SECURE_2021_HISTORICAL":
        "raw/policies/hdfc_ergo/"
        "hdfc_optima_secure_2021_HISTORICAL_extracted_text.txt",

    "IRDAI_MASTER_CIRCULAR_2024":
        "raw/regulatory/irdai/"
        "irdai_master_circular_2024_extracted_text.txt",

    "CARE_SUPREME_2026_POLICY":
        "processed/policies/care/"
        "care_supreme_policy_extracted_text.txt",
}


# ================================================================
# FASTAPI APPLICATION
# ================================================================

app = FastAPI(
    title=(
        "Explainable Pre-Submission Health Insurance "
        "Claim Rule Validator"
    ),

    description=(
        "Checks a claim against documented, source-cited "
        "health insurance policy rules and produces "
        "PASS / WARNING / PARTIAL_DEDUCTION / FAIL "
        "per rule, with an overall "
        "SUBMISSION_READY / HUMAN_REVIEW_NEEDED / "
        "FIX_BEFORE_SUBMISSION recommendation. "
        "This system is not an insurer approval or rejection "
        "predictor and is not connected to NHCX. "
        "Financial output is a rule-based estimate and is "
        "not a guaranteed insurer payout. "
        "Test claims are synthetic. "
        "ICD-10 diagnosis lookup uses a locally seeded "
        "WHO ICD-10 dataset."
    ),
)


# ================================================================
# RESPONSE SHAPING
# ================================================================

def _nest_source(results):
    """
    Convert the engine's internal flat provenance fields:

        source_document
        source_page
        source_section

    into the API contract:

        source:
            document
            page
    """

    out = []

    for r in results:

        out.append({
            "rule_id": r["rule_id"],
            "category": r["category"],
            "severity": r["severity"],
            "reason": r["reason"],
            "expected": r["expected"],
            "actual": r["actual"],

            "source": {
                "document": r.get("source_document"),
                "page": r.get("source_page"),
            },

            "provenance": r.get("provenance"),
        })

    return out


# ================================================================
# SHARED HEALTH HANDLER
# ================================================================

def _health():

    return {
        "status": "ok"
    }


# ================================================================
# LIST POLICIES
# ================================================================

def _list_policies(
    db: Session,
):

    out = []

    policies = db.query(Policy).all()

    for p in policies:

        out.append({
            "policy_id": p.id,

            "insurer": (
                p.insurer.name
                if p.insurer
                else None
            ),

            "product": p.product_name,

            "versions": [
                {
                    "policy_version_id":
                        v.policy_version_id,

                    "uin":
                        v.uin,

                    "status":
                        v.status,

                    "uin_conflict_flag":
                        v.uin_conflict_flag,
                }

                for v in p.versions
            ],
        })

    return out


# ================================================================
# GET POLICY
# ================================================================

def _get_policy(
    policy_id: int,
    db: Session,
):

    p = db.query(Policy).get(policy_id)

    if not p:

        raise HTTPException(
            status_code=404,
            detail="policy not found",
        )

    return {
        "policy_id": p.id,

        "insurer": (
            p.insurer.name
            if p.insurer
            else None
        ),

        "product": p.product_name,

        "versions": [
            {
                "policy_version_id":
                    v.policy_version_id,

                "uin":
                    v.uin,

                "status":
                    v.status,

                "uin_conflict_flag":
                    v.uin_conflict_flag,
            }

            for v in p.versions
        ],
    }


# ================================================================
# POLICY RULES
# ================================================================

def _policy_rules(
    policy_id: int,
    db: Session,
):

    p = db.query(Policy).get(policy_id)

    if not p:

        raise HTTPException(
            status_code=404,
            detail="policy not found",
        )

    out = []

    for v in p.versions:

        rules = (
            db.query(PolicyRule)
            .filter_by(
                policy_version_db_id=v.id
            )
            .all()
        )

        out.append({
            "policy_version_id":
                v.policy_version_id,

            "rules": [
                {
                    "candidate_id":
                        r.candidate_id,

                    "rule_type":
                        r.rule_type,

                    "rule_name":
                        r.rule_name,

                    "value":
                        r.value,

                    "unit":
                        r.unit,

                    "condition":
                        r.condition,

                    "exception":
                        r.exception,

                    "source_document":
                        r.source_document,

                    "source_page":
                        r.source_page,

                    "source_text":
                        r.source_text,

                    "provenance":
                        r.provenance,

                    "review_status":
                        r.review_status,
                }

                for r in rules
            ],
        })

    return out


# ================================================================
# POLICY SOURCES
# ================================================================

def _policy_sources(
    policy_id: int,
    db: Session,
):

    p = db.query(Policy).get(policy_id)

    if not p:

        raise HTTPException(
            status_code=404,
            detail="policy not found",
        )

    doc_ids = set()

    for v in p.versions:

        rules = (
            db.query(PolicyRule)
            .filter_by(
                policy_version_db_id=v.id
            )
            .all()
        )

        for r in rules:

            if r.source_document:

                doc_ids.add(
                    r.source_document
                )

    if not doc_ids:

        return []

    docs = (
        db.query(Document)
        .filter(
            Document.document_id.in_(doc_ids)
        )
        .all()
    )

    return [
        {
            "document_id":
                d.document_id,

            "source_url":
                d.source_url,

            "hash_type":
                d.hash_type,

            "sha256":
                d.sha256,

            "page_count":
                d.page_count,
        }

        for d in docs
    ]


# ================================================================
# LIST CLAIMS
# ================================================================

def _list_claims(
    db: Session,
):

    claims = (
        db.query(Claim)
        .order_by(
            Claim.id.desc()
        )
        .all()
    )

    out = []

    for c in claims:

        pv = (
            db.query(PolicyVersion)
            .get(
                c.policy_version_db_id
            )
        )

        policy = (
            pv.policy
            if pv
            else None
        )

        latest_run = (
            db.query(ValidationRun)
            .filter_by(
                claim_id=c.id
            )
            .order_by(
                ValidationRun.id.desc()
            )
            .first()
        )

        out.append({
            "claim_id":
                c.id,

            "claim_ref":
                c.claim_ref,

            "insurer":
                (
                    policy.insurer.name
                    if policy and policy.insurer
                    else None
                ),

            "product":
                (
                    policy.product_name
                    if policy
                    else None
                ),

            "policy_version_id":
                (
                    pv.policy_version_id
                    if pv
                    else None
                ),

            "admission_date":
                (
                    str(c.admission_date)
                    if c.admission_date
                    else None
                ),

            "billed_amount":
                (
                    str(c.billed_amount)
                    if c.billed_amount is not None
                    else None
                ),

            "claim_provenance":
                c.claim_provenance,

            "last_validation_result":
                (
                    latest_run.overall_result
                    if latest_run
                    else None
                ),
        })

    return out


# ================================================================
# CREATE CLAIM
# ================================================================

def _create_claim(
    claim_in: ClaimCreate,
    db: Session,
):

    # ------------------------------------------------------------
    # Resolve external policy_version_id
    # to internal database id
    # ------------------------------------------------------------

    pv = (
        db.query(PolicyVersion)
        .filter_by(
            policy_version_id=
                claim_in.policy_version_id
        )
        .first()
    )

    if not pv:

        raise HTTPException(
            status_code=400,
            detail=(
                "Unknown policy_version_id: "
                f"{claim_in.policy_version_id}"
            ),
        )

    # ------------------------------------------------------------
    # Convert Pydantic model to SQLAlchemy fields
    # ------------------------------------------------------------

    data = claim_in.model_dump(
        exclude={
            "policy_version_id"
        }
    )

    # ------------------------------------------------------------
    # Create claim
    # ------------------------------------------------------------

    try:

        claim = Claim(
            policy_version_db_id=pv.id,
            **data,
        )

        db.add(claim)
        db.commit()
        db.refresh(claim)

    except Exception:

        db.rollback()
        raise

    return {
        "claim_id":
            claim.id,

        "claim_ref":
            claim.claim_ref,

        "policy_version_id":
            pv.policy_version_id,

        "message":
            "Claim created successfully. "
            "Run validation before submission.",
    }


# ================================================================
# UPDATE CLAIM / MISSING DATA
# ================================================================

def _update_claim(
    claim_id: int,
    claim_in: ClaimUpdate,
    db: Session,
):
    """
    Update only the fields supplied by the user.

    This is intentionally a PATCH-style update.

    Example:

        {
            "room_rent_per_day": 5000,
            "billed_amount": 125000,
            "diagnosis_code": "J18.9"
        }

    Existing fields that are NOT supplied remain unchanged.

    policy_version_id cannot be changed here because validation
    must remain tied to the policy version under which the claim
    was originally created.
    """

    # ------------------------------------------------------------
    # Find claim
    # ------------------------------------------------------------

    claim = (
        db.query(Claim)
        .get(claim_id)
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="claim not found",
        )

    # ------------------------------------------------------------
    # Get only explicitly supplied fields
    #
    # This is VERY important.
    #
    # exclude_unset=True means:
    #
    #     omitted field -> DO NOT MODIFY
    #
    # while:
    #
    #     field: null -> explicitly set NULL
    # ------------------------------------------------------------

    update_data = claim_in.model_dump(
        exclude_unset=True
    )

    # ------------------------------------------------------------
    # Never allow policy version to be changed
    # through a missing-data update.
    # ------------------------------------------------------------

    if "policy_version_id" in update_data:

        raise HTTPException(
            status_code=400,
            detail=(
                "policy_version_id cannot be changed during "
                "claim update. Create a new claim if the "
                "policy version is incorrect."
            ),
        )

    if not update_data:

        raise HTTPException(
            status_code=400,
            detail=(
                "No fields supplied for update."
            ),
        )

    # ------------------------------------------------------------
    # Update fields
    # ------------------------------------------------------------

    updated_fields = []

    try:

        for field, value in update_data.items():

            # Make sure the field actually exists
            # on the SQLAlchemy Claim model.

            if not hasattr(claim, field):

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid claim field: {field}"
                    ),
                )

            setattr(
                claim,
                field,
                value,
            )

            updated_fields.append(field)

        db.commit()
        db.refresh(claim)

    except HTTPException:

        db.rollback()
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update claim: "
                f"{str(e)}"
            ),
        )

    # ------------------------------------------------------------
    # Return updated information
    # ------------------------------------------------------------

    pv = (
        db.query(PolicyVersion)
        .get(
            claim.policy_version_db_id
        )
    )

    return {
        "claim_id":
            claim.id,

        "claim_ref":
            claim.claim_ref,

        "updated_fields":
            updated_fields,

        "policy_version_id":
            (
                pv.policy_version_id
                if pv
                else None
            ),

        "message":
            (
                "Claim data updated successfully. "
                "Run validation again to evaluate the "
                "updated claim."
            ),
    }


# ================================================================
# GET CLAIM
# ================================================================

def _get_claim(
    claim_id: int,
    db: Session,
):

    claim = (
        db.query(Claim)
        .get(claim_id)
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="claim not found",
        )

    pv = (
        db.query(PolicyVersion)
        .get(
            claim.policy_version_db_id
        )
    )

    return {
        "claim_id":
            claim.id,

        "claim_ref":
            claim.claim_ref,

        "policy_version_db_id":
            claim.policy_version_db_id,

        "policy_version_id":
            (
                pv.policy_version_id
                if pv
                else None
            ),

        "policy_start_date":
            (
                str(claim.policy_start_date)
                if claim.policy_start_date
                else None
            ),

        "policy_end_date":
            (
                str(claim.policy_end_date)
                if claim.policy_end_date
                else None
            ),

        "sum_insured":
            claim.sum_insured,

        "insured_age_at_entry":
            claim.insured_age_at_entry,

        "patient_ref":
            claim.patient_ref,

        "date_of_birth":
            (
                str(claim.date_of_birth)
                if claim.date_of_birth
                else None
            ),

        "gender":
            claim.gender,

        "hospital_id":
            claim.hospital_id,

        "hospital_type":
            claim.hospital_type,

        "hospital_registration_number":
            claim.hospital_registration_number,

        "ip_registration_number":
            claim.ip_registration_number,

        "admission_date":
            (
                str(claim.admission_date)
                if claim.admission_date
                else None
            ),

        "admission_time":
            claim.admission_time,

        "discharge_date":
            (
                str(claim.discharge_date)
                if claim.discharge_date
                else None
            ),

        "discharge_time":
            claim.discharge_time,

        "admission_type":
            claim.admission_type,

        "claim_type":
            claim.claim_type,

        "discharge_status":
            claim.discharge_status,

        "diagnosis_code":
            claim.diagnosis_code,

        "diagnosis_description":
            claim.diagnosis_description,

        "additional_diagnoses":
            claim.additional_diagnoses,

        "comorbidities":
            claim.comorbidities,

        "procedure_description":
            claim.procedure_description,

        "procedure_code":
            claim.procedure_code,

        "procedure_2_description":
            claim.procedure_2_description,

        "procedure_2_code":
            claim.procedure_2_code,

        "procedure_3_description":
            claim.procedure_3_description,

        "procedure_3_code":
            claim.procedure_3_code,

        "room_type":
            claim.room_type,

        "room_rent_per_day":
            claim.room_rent_per_day,

        "billed_amount":
            claim.billed_amount,

        "treatment_category":
            claim.treatment_category,

        "category_billed_amount":
            claim.category_billed_amount,

        "preauth_status":
            claim.preauth_status,

        "preauth_number":
            claim.preauth_number,

        "preauth_request_date":
            (
                str(claim.preauth_request_date)
                if claim.preauth_request_date
                else None
            ),

        "preauth_approval_date":
            (
                str(claim.preauth_approval_date)
                if claim.preauth_approval_date
                else None
            ),

        "notification_date":
            (
                str(claim.notification_date)
                if claim.notification_date
                else None
            ),

        "claim_filed_date":
            (
                str(claim.claim_filed_date)
                if claim.claim_filed_date
                else None
            ),

        "injury_related":
            claim.injury_related,

        "self_inflicted_injury":
            claim.self_inflicted_injury,

        "substance_abuse_related":
            claim.substance_abuse_related,

        "substance_abuse_test_done":
            claim.substance_abuse_test_done,

        "medico_legal_case":
            claim.medico_legal_case,

        "police_reported":
            claim.police_reported,

        "fir_number":
            claim.fir_number,

        "delivery_date":
            (
                str(claim.delivery_date)
                if claim.delivery_date
                else None
            ),

        "gravida_status":
            claim.gravida_status,

        "deductible_opted":
            claim.deductible_opted,

        "deductible_amount_opted":
            claim.deductible_amount_opted,

        "documents_submitted":
            claim.documents_submitted,

        "claim_provenance":
            claim.claim_provenance,
    }


# ================================================================
# VALIDATE CLAIM
# ================================================================

def _validate(
    claim_id: int,
    db: Session,
):

    claim = (
        db.query(Claim)
        .get(claim_id)
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="claim not found",
        )

    # ------------------------------------------------------------
    # IMPORTANT:
    #
    # validate_claim() always reads the CURRENT database state.
    #
    # Therefore, after PATCH /claims/{id}, calling this endpoint
    # automatically validates the updated information.
    # ------------------------------------------------------------

    run, results, financials = validate_claim(
        db,
        claim,
    )

    return {
        "overall_result":
            run.overall_result,

        "results":
            _nest_source(results),

        "financials":
            financials,
    }


# ================================================================
# GET LATEST VALIDATION
# ================================================================

def _get_latest_validation(
    claim_id: int,
    db: Session,
):

    claim = (
        db.query(Claim)
        .get(claim_id)
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="claim not found",
        )

    run = (
        db.query(ValidationRun)
        .filter_by(
            claim_id=claim_id
        )
        .order_by(
            ValidationRun.id.desc()
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=404,
            detail=(
                "no validation run yet for this claim; "
                "POST /claims/{claim_id}/validate first"
            ),
        )

    results = (
        db.query(ValidationResult)
        .filter_by(
            validation_run_id=run.id
        )
        .all()
    )

    flat = [
        {
            "rule_id":
                r.rule_id,

            "category":
                r.category,

            "severity":
                r.severity,

            "reason":
                r.reason,

            "expected":
                r.expected,

            "actual":
                r.actual,

            "source_document":
                r.source_document,

            "source_page":
                r.source_page,

            "source_section":
                r.source_section,

            "provenance":
                r.provenance,
        }

        for r in results
    ]

    return {
        "overall_result":
            run.overall_result,

        "results":
            _nest_source(flat),

        # ValidationRun currently does not persist
        # the financial dictionary.
        "financials":
            None,
    }


# =================================================================
# LEGACY /api/* ROUTES
# =================================================================

@app.get("/api/health")
def api_health():

    return _health()


@app.get("/api/policies")
def api_list_policies(
    db: Session = Depends(get_db),
):

    return _list_policies(db)


@app.get("/api/policies/{policy_id}/versions")
def api_policy_versions(
    policy_id: int,
    db: Session = Depends(get_db),
):

    return _get_policy(
        policy_id,
        db,
    )["versions"]


@app.get("/api/policies/{policy_id}/rules")
def api_policy_rules(
    policy_id: int,
    db: Session = Depends(get_db),
):

    return _policy_rules(
        policy_id,
        db,
    )


@app.get("/api/policies/{policy_id}/sources")
def api_policy_sources(
    policy_id: int,
    db: Session = Depends(get_db),
):

    return _policy_sources(
        policy_id,
        db,
    )


@app.post("/api/claims")
def api_create_claim(
    claim_in: ClaimCreate,
    db: Session = Depends(get_db),
):

    return _create_claim(
        claim_in,
        db,
    )


# ---------------------------------------------------------------
# LEGACY UPDATE CLAIM
# ---------------------------------------------------------------

@app.patch("/api/claims/{claim_id}")
def api_update_claim(
    claim_id: int,
    claim_in: ClaimUpdate,
    db: Session = Depends(get_db),
):

    return _update_claim(
        claim_id,
        claim_in,
        db,
    )


@app.get("/api/claims/{claim_id}")
def api_get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
):

    return _get_claim(
        claim_id,
        db,
    )


@app.post("/api/claims/{claim_id}/validate")
def api_validate(
    claim_id: int,
    db: Session = Depends(get_db),
):

    claim = (
        db.query(Claim)
        .get(claim_id)
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="claim not found",
        )

    run, results, financials = validate_claim(
        db,
        claim,
    )

    # Legacy route intentionally retains
    # the flat source shape.

    return {
        "overall_result":
            run.overall_result,

        "results":
            results,

        "financials":
            financials,
    }


@app.get("/api/claims/{claim_id}/validation")
def api_get_latest_validation(
    claim_id: int,
    db: Session = Depends(get_db),
):

    claim = (
        db.query(Claim)
        .get(claim_id)
    )

    if not claim:

        raise HTTPException(
            status_code=404,
            detail="claim not found",
        )

    run = (
        db.query(ValidationRun)
        .filter_by(
            claim_id=claim_id
        )
        .order_by(
            ValidationRun.id.desc()
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=404,
            detail=(
                "no validation run yet for this claim; "
                "POST /api/claims/{claim_id}/validate first"
            ),
        )

    results = (
        db.query(ValidationResult)
        .filter_by(
            validation_run_id=run.id
        )
        .all()
    )

    return {
        "overall_result":
            run.overall_result,

        "results": [
            {
                "rule_id":
                    r.rule_id,

                "category":
                    r.category,

                "severity":
                    r.severity,

                "reason":
                    r.reason,

                "expected":
                    r.expected,

                "actual":
                    r.actual,

                "source_document":
                    r.source_document,

                "source_page":
                    r.source_page,

                "source_section":
                    r.source_section,

                "provenance":
                    r.provenance,
            }

            for r in results
        ],

        "financials":
            None,
    }


# =================================================================
# ROOT-LEVEL ROUTES
# =================================================================

@app.get("/health")
def health():

    return _health()


@app.get("/policies")
def list_policies(
    db: Session = Depends(get_db),
):

    return _list_policies(db)


@app.get("/policies/{policy_id}")
def get_policy(
    policy_id: int,
    db: Session = Depends(get_db),
):

    return _get_policy(
        policy_id,
        db,
    )


@app.get("/policies/{policy_id}/rules")
def policy_rules(
    policy_id: int,
    db: Session = Depends(get_db),
):

    return _policy_rules(
        policy_id,
        db,
    )


@app.get("/policies/{policy_id}/sources")
def policy_sources(
    policy_id: int,
    db: Session = Depends(get_db),
):

    return _policy_sources(
        policy_id,
        db,
    )


# =================================================================
# DOCUMENT TEXT
# =================================================================

@app.get("/documents/{document_id}/text")
def get_document_text(
    document_id: str,
    db: Session = Depends(get_db),
):

    """
    Serves the REAL extracted text associated
    with a source document.

    The endpoint never fabricates or paraphrases
    source text.
    """

    doc = (
        db.query(Document)
        .filter_by(
            document_id=document_id
        )
        .first()
    )

    if not doc:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown document_id: "
                f"{document_id}"
            ),
        )

    rel_path = (
        doc.extracted_text_path
        or _DOCUMENT_TEXT_FILES.get(
            document_id
        )
    )

    if not rel_path:

        raise HTTPException(
            status_code=404,
            detail=(
                "No extracted-text file is mapped "
                f"for document_id: {document_id}"
            ),
        )

    abs_path = os.path.join(
        _DATA_ROOT,
        rel_path,
    )

    if not os.path.exists(abs_path):

        raise HTTPException(
            status_code=404,
            detail=(
                "Extracted-text file not found "
                f"on disk: {rel_path}"
            ),
        )

    with open(
        abs_path,
        "r",
        encoding="utf-8",
    ) as f:

        text = f.read()

    return {
        "document_id":
            document_id,

        "source_url":
            doc.source_url,

        "hash_type":
            doc.hash_type,

        "page_count":
            doc.page_count,

        "text":
            text,
    }


# =================================================================
# SINGLE RULE
# =================================================================

@app.get("/rules/{candidate_id}")
def get_rule_by_candidate_id(
    candidate_id: str,
    db: Session = Depends(get_db),
):

    r = (
        db.query(PolicyRule)
        .filter_by(
            candidate_id=candidate_id
        )
        .first()
    )

    if not r:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown candidate_id: "
                f"{candidate_id}"
            ),
        )

    return {
        "candidate_id":
            r.candidate_id,

        "rule_type":
            r.rule_type,

        "rule_name":
            r.rule_name,

        "condition":
            r.condition,

        "value":
            r.value,

        "unit":
            r.unit,

        "applies_to":
            r.applies_to,

        "exception":
            r.exception,

        "source_document":
            r.source_document,

        "source_page":
            r.source_page,

        "source_section":
            r.source_section,

        "source_text":
            r.source_text,

        "extraction_method":
            r.extraction_method,

        "confidence":
            r.confidence,

        "review_status":
            r.review_status,

        "provenance":
            r.provenance,
    }


# =================================================================
# CLAIM ROUTES
# =================================================================

@app.post("/claims")
def create_claim(
    claim_in: ClaimCreate,
    db: Session = Depends(get_db),
):

    return _create_claim(
        claim_in,
        db,
    )


@app.get("/claims")
def list_claims(
    db: Session = Depends(get_db),
):

    return _list_claims(db)


# -----------------------------------------------------------------
# GET CLAIM
# -----------------------------------------------------------------

@app.get("/claims/{claim_id}")
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
):

    return _get_claim(
        claim_id,
        db,
    )


# -----------------------------------------------------------------
# UPDATE MISSING CLAIM DATA
# -----------------------------------------------------------------

@app.patch("/claims/{claim_id}")
def update_claim(
    claim_id: int,
    claim_in: ClaimUpdate,
    db: Session = Depends(get_db),
):

    return _update_claim(
        claim_id,
        claim_in,
        db,
    )


# -----------------------------------------------------------------
# RE-VALIDATE CLAIM
# -----------------------------------------------------------------

@app.post(
    "/claims/{claim_id}/validate",
    response_model=ValidationRunOut,
)
def validate(
    claim_id: int,
    db: Session = Depends(get_db),
):

    return _validate(
        claim_id,
        db,
    )


# -----------------------------------------------------------------
# GET LATEST VALIDATION
# -----------------------------------------------------------------

@app.get(
    "/claims/{claim_id}/validation",
    response_model=ValidationRunOut,
)
def get_latest_validation(
    claim_id: int,
    db: Session = Depends(get_db),
):

    return _get_latest_validation(
        claim_id,
        db,
    )

# =================================================================
# POLICY UPLOAD (PDF -> TEXT -> LLM RULE EXTRACTION)
# =================================================================

def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").upper()
    return text


def _upload_policy(
    insurer: str,
    product: str,
    uin: str,
    policy_version_id: str,
    document_type: str,
    file_bytes: bytes,
    db: Session,
):
    ins = db.query(Insurer).filter_by(name=insurer).first()
    if not ins:
        ins = Insurer(name=insurer)
        db.add(ins)
        db.flush()

    pol = (
        db.query(Policy)
        .filter_by(insurer_id=ins.id, product_name=product)
        .first()
    )
    if not pol:
        pol = Policy(insurer_id=ins.id, product_name=product)
        db.add(pol)
        db.flush()

    pv = (
        db.query(PolicyVersion)
        .filter_by(policy_version_id=policy_version_id)
        .first()
    )
    if not pv:
        pv = PolicyVersion(
            policy_id=pol.id,
            policy_version_id=policy_version_id,
            uin=uin,
            status="ACTIVE",
            uin_conflict_flag=False,
        )
        db.add(pv)
        db.flush()

    full_text, page_count = extract_text_with_pages(file_bytes)
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    document_id = (
        f"{_slugify(insurer)}_{_slugify(product)}_"
        f"{uuid.uuid4().hex[:8]}"
    )

    upload_dir = os.path.join(
        _DATA_ROOT,
        "raw",
        "policies",
        "uploaded"
    )
    os.makedirs(upload_dir, exist_ok=True)

    pdf_path = os.path.join(
        upload_dir,
        f"{document_id}.pdf"
    )

    with open(pdf_path, "wb") as f:
        f.write(file_bytes)

    text_path = os.path.join(
        upload_dir,
        f"{document_id}.txt"
    )

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    text_rel_path = os.path.relpath(
        text_path,
        _DATA_ROOT
    )

    doc = Document(
        document_id=document_id,
        policy_version_db_id=pv.id,
        document_type=document_type,
        source_url=None,
        sha256=sha256,
        hash_type="ORIGINAL_FILE",
        original_file_available=True,
        page_count=page_count,
        status="ACTIVE",
        notes=(
            "Uploaded via frontend. Text extracted with PyMuPDF; "
            "rules extracted with Groq LLM. All extracted rules stored "
            "with review_status=PENDING for manual review."
        ),
        extracted_text_path=text_rel_path,
    )

    db.add(doc)
    db.flush()

    extracted = extract_rules_from_text(
        full_text,
        pages_per_chunk=1
    )

    created_rules = []

    for i, r in enumerate(extracted, start=1):
        candidate_id = f"UP-{document_id}-{i:03d}"

        rule = PolicyRule(
            candidate_id=candidate_id,
            policy_version_db_id=pv.id,
            rule_type=r.get(
                "rule_type",
                "DOCUMENTATION_MISSING"
            ),
            rule_name=r.get("rule_name", ""),
            condition=r.get("condition", ""),
            value=r.get("value", ""),
            unit=r.get("unit", ""),
            applies_to=r.get("applies_to", ""),
            exception=r.get("exception", ""),
            source_document=document_id,
            source_page=r.get("source_page", ""),
            source_section=r.get("source_section", ""),
            source_text=r.get("source_text", ""),
            extraction_method=(
                "LLM_EXTRACTION_FROM_UPLOADED_PDF"
            ),
            confidence=r.get(
                "confidence",
                "LOW"
            ),
            review_status="PENDING",
            provenance="INSURER_DOCUMENT",
        )

        db.add(rule)

        created_rules.append({
            "candidate_id": candidate_id,
            "rule_type": rule.rule_type,
            "rule_name": rule.rule_name,
            "value": rule.value,
            "unit": rule.unit,
            "source_page": rule.source_page,
            "source_text": rule.source_text,
            "confidence": rule.confidence,
        })

    db.commit()

    return {
        "document_id": document_id,
        "policy_version_id": pv.policy_version_id,
        "page_count": page_count,
        "rules_extracted": len(created_rules),
        "rules": created_rules,
        "message": (
            "Upload complete. All extracted rules were stored "
            "with review_status=PENDING for manual review."
        ),
    }


@app.post("/policies/upload")
async def upload_policy(
    insurer: str = Form(...),
    product: str = Form(...),
    uin: str = Form(...),
    policy_version_id: str = Form(...),
    document_type: str = Form("POLICY_WORDING"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    try:
        return _upload_policy(
            insurer=insurer,
            product=product,
            uin=uin,
            policy_version_id=policy_version_id,
            document_type=document_type,
            file_bytes=file_bytes,
            db=db,
        )

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Upload processing failed: {str(e)}",
        )


# =================================================================
# ADDITIONAL ROUTERS
# =================================================================
# =================================================================
# ADDITIONAL ROUTERS
# =================================================================

# QA / policy question-answering endpoints
app.include_router(
    qa_router
)


# Local WHO ICD-10 lookup endpoints.
#
# Expected router:
#     app/api/icd10.py
#
# This router searches the locally seeded ICD10Code table
# rather than calling the WHO API for every request.

app.include_router(
    icd10_router
)