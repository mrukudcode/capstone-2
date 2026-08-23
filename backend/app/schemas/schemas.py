from pydantic import BaseModel
from datetime import date
from typing import Optional, List


class ClaimCreate(BaseModel):
    claim_ref: str
    policy_version_id: str  # e.g. "star_assure_2026_v1" (string key, not DB int id)
    policy_start_date: date
    policy_end_date: Optional[date] = None
    patient_ref: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    hospital_id: Optional[str] = None
    procedure_description: Optional[str] = None
    procedure_code: Optional[str] = None
    admission_date: date
    discharge_date: Optional[date] = None
    room_type: Optional[str] = None
    room_rent_per_day: Optional[float] = None
    diagnosis_code: Optional[str] = None
    diagnosis_description: Optional[str] = None
    billed_amount: Optional[float] = None
    preauth_status: Optional[str] = "NONE"
    claim_type: Optional[str] = None  # EMERGENCY | PLANNED
    preauth_request_date: Optional[date] = None
    claim_filed_date: Optional[date] = None
    notification_date: Optional[date] = None
    sum_insured: Optional[float] = None
    insured_age_at_entry: Optional[int] = None
    treatment_category: Optional[str] = None
    category_billed_amount: Optional[float] = None
    deductible_opted: Optional[bool] = False
    deductible_amount_opted: Optional[float] = None
    documents_submitted: Optional[str] = None
    policy_cancelled_date: Optional[date] = None
    claim_provenance: Optional[str] = "SYNTHETIC"


class ValidationResultSource(BaseModel):
    document: Optional[str]
    page: Optional[str]


class ValidationResultOut(BaseModel):
    rule_id: str
    category: str
    severity: str
    reason: str
    expected: str
    actual: str
    source: ValidationResultSource
    provenance: Optional[str]

    class Config:
        from_attributes = True


class ValidationRunOut(BaseModel):
    overall_result: str
    results: List[ValidationResultOut]
    financials: Optional[dict] = None
