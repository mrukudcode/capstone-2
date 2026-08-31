from pydantic import BaseModel
from datetime import date
from typing import Optional, List, Dict, Any


# ================================================================
# CLAIM CREATE
# ================================================================

class ClaimCreate(BaseModel):

    # ============================================================
    # CLAIM / POLICY DETAILS
    # ============================================================

    claim_ref: str
    policy_version_id: str

    policy_start_date: date
    policy_end_date: Optional[date] = None
    policy_cancelled_date: Optional[date] = None

    sum_insured: Optional[float] = None
    insured_age_at_entry: Optional[int] = None

    # ============================================================
    # PREVIOUS INSURANCE / CONTINUITY
    # ============================================================

    previous_insurer_name: Optional[str] = None
    previous_policy_start_date: Optional[date] = None
    previous_policy_end_date: Optional[date] = None
    continuous_coverage_since: Optional[date] = None

    # ============================================================
    # PATIENT DETAILS
    # ============================================================

    patient_ref: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

    # ============================================================
    # HOSPITAL DETAILS
    # ============================================================

    hospital_id: Optional[str] = None
    hospital_type: Optional[str] = None
    hospital_registration_number: Optional[str] = None
    ip_registration_number: Optional[str] = None

    # ============================================================
    # HOSPITALISATION DETAILS
    # ============================================================

    admission_date: date
    discharge_date: Optional[date] = None

    admission_type: Optional[str] = None
    claim_type: Optional[str] = None

    admission_time: Optional[str] = None
    discharge_time: Optional[str] = None
    discharge_status: Optional[str] = None

    # ============================================================
    # DIAGNOSIS
    # ============================================================

    diagnosis_code: Optional[str] = None
    diagnosis_description: Optional[str] = None
    additional_diagnoses: Optional[str] = None
    comorbidities: Optional[str] = None

    # ============================================================
    # PROCEDURES
    # ============================================================

    procedure_description: Optional[str] = None
    procedure_code: Optional[str] = None

    procedure_2_description: Optional[str] = None
    procedure_2_code: Optional[str] = None

    procedure_3_description: Optional[str] = None
    procedure_3_code: Optional[str] = None

    # ============================================================
    # ROOM / HOSPITAL CHARGES
    # ============================================================

    room_type: Optional[str] = None
    room_rent_per_day: Optional[float] = None
    billed_amount: Optional[float] = None

    # ============================================================
    # TREATMENT CATEGORY
    # ============================================================

    treatment_category: Optional[str] = None
    category_billed_amount: Optional[float] = None

    # ============================================================
    # PREAUTHORIZATION
    # ============================================================

    preauth_status: Optional[str] = "NONE"
    preauth_number: Optional[str] = None
    preauth_request_date: Optional[date] = None
    preauth_approval_date: Optional[date] = None

    # ============================================================
    # CLAIM NOTIFICATION / SUBMISSION
    # ============================================================

    notification_date: Optional[date] = None
    claim_filed_date: Optional[date] = None

    # ============================================================
    # INJURY / EXCLUSION INFORMATION
    # ============================================================

    injury_related: Optional[bool] = None
    self_inflicted_injury: Optional[bool] = None

    substance_abuse_related: Optional[bool] = None
    substance_abuse_test_done: Optional[bool] = None

    # ============================================================
    # MEDICO-LEGAL CASE
    # ============================================================

    medico_legal_case: Optional[bool] = None
    police_reported: Optional[bool] = None
    fir_number: Optional[str] = None

    # ============================================================
    # MATERNITY
    # ============================================================

    delivery_date: Optional[date] = None
    gravida_status: Optional[str] = None

    # ============================================================
    # DEDUCTIBLE
    # ============================================================

    deductible_opted: Optional[bool] = False
    deductible_amount_opted: Optional[float] = None

    # ============================================================
    # DOCUMENTS
    # ============================================================

    documents_submitted: Optional[str] = None
    policy_document_received_date:   Optional[date] = None
    additional_clinical_details: Optional[str] = None

    # ============================================================
    # PROVENANCE
    # ============================================================

    claim_provenance: Optional[str] = "SYNTHETIC"


# ================================================================
# CLAIM UPDATE
# ================================================================

class ClaimUpdate(BaseModel):
    """
    Partial update schema.

    Used when a validation result identifies missing information
    and the user supplies the missing claim data.

    Only fields supplied by the user are updated.
    Existing claim values are preserved.
    """

    policy_end_date: Optional[date] = None
    policy_cancelled_date: Optional[date] = None

    sum_insured: Optional[float] = None
    insured_age_at_entry: Optional[int] = None

    previous_insurer_name: Optional[str] = None
    previous_policy_start_date: Optional[date] = None
    previous_policy_end_date: Optional[date] = None
    continuous_coverage_since: Optional[date] = None

    patient_ref: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

    hospital_id: Optional[str] = None
    hospital_type: Optional[str] = None
    hospital_registration_number: Optional[str] = None
    ip_registration_number: Optional[str] = None

    discharge_date: Optional[date] = None

    admission_type: Optional[str] = None
    claim_type: Optional[str] = None

    admission_time: Optional[str] = None
    discharge_time: Optional[str] = None
    discharge_status: Optional[str] = None

    diagnosis_code: Optional[str] = None
    diagnosis_description: Optional[str] = None
    additional_diagnoses: Optional[str] = None
    comorbidities: Optional[str] = None

    procedure_description: Optional[str] = None
    procedure_code: Optional[str] = None

    procedure_2_description: Optional[str] = None
    procedure_2_code: Optional[str] = None

    procedure_3_description: Optional[str] = None
    procedure_3_code: Optional[str] = None

    room_type: Optional[str] = None
    room_rent_per_day: Optional[float] = None

    billed_amount: Optional[float] = None

    treatment_category: Optional[str] = None
    category_billed_amount: Optional[float] = None

    preauth_status: Optional[str] = None
    preauth_number: Optional[str] = None
    preauth_request_date: Optional[date] = None
    preauth_approval_date: Optional[date] = None

    notification_date: Optional[date] = None
    claim_filed_date: Optional[date] = None

    injury_related: Optional[bool] = None
    self_inflicted_injury: Optional[bool] = None

    substance_abuse_related: Optional[bool] = None
    substance_abuse_test_done: Optional[bool] = None

    medico_legal_case: Optional[bool] = None
    police_reported: Optional[bool] = None
    fir_number: Optional[str] = None

    delivery_date: Optional[date] = None
    gravida_status: Optional[str] = None

    deductible_opted: Optional[bool] = None
    deductible_amount_opted: Optional[float] = None

    documents_submitted: Optional[str] = None

    claim_provenance: Optional[str] = None


# ================================================================
# VALIDATION SOURCE
# ================================================================

class ValidationResultSource(BaseModel):

    document: Optional[str] = None
    page: Optional[str] = None


# ================================================================
# VALIDATION RESULT OUTPUT
# ================================================================

class ValidationResultOut(BaseModel):

    rule_id: str
    category: str
    severity: str

    reason: str
    expected: str
    actual: str

    source: ValidationResultSource

    provenance: Optional[str] = None

    class Config:
        from_attributes = True


# ================================================================
# VALIDATION RUN OUTPUT
# ================================================================

class ValidationRunOut(BaseModel):

    overall_result: str

    results: List[ValidationResultOut]

    financials: Optional[Dict[str, Any]] = None