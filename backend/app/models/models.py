"""
SQLAlchemy models for the Provenance-First Indian Health Insurance
Claim Validator.

Uses SQLite for the current implementation.

The ORM layer can later be migrated to PostgreSQL by changing the
database connection configuration.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Boolean,
)

from sqlalchemy.orm import relationship, declarative_base

import datetime


Base = declarative_base()


# ================================================================
# INSURER
# ================================================================

class Insurer(Base):
    __tablename__ = "insurers"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String,
        nullable=False,
        unique=True
    )

    products = relationship(
        "Policy",
        back_populates="insurer"
    )


# ================================================================
# POLICY
# ================================================================

class Policy(Base):
    __tablename__ = "policies"

    id = Column(
        Integer,
        primary_key=True
    )

    insurer_id = Column(
        Integer,
        ForeignKey("insurers.id"),
        nullable=False
    )

    product_name = Column(
        String,
        nullable=False
    )

    insurer = relationship(
        "Insurer",
        back_populates="products"
    )

    versions = relationship(
        "PolicyVersion",
        back_populates="policy"
    )


# ================================================================
# POLICY VERSION
# ================================================================

class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id = Column(
        Integer,
        primary_key=True
    )

    policy_id = Column(
        Integer,
        ForeignKey("policies.id"),
        nullable=False
    )

    policy_version_id = Column(
        String,
        nullable=False,
        unique=True
    )

    uin = Column(
        String,
        nullable=False
    )

    status = Column(
        String,
        default="ACTIVE"
    )

    uin_conflict_flag = Column(
        Boolean,
        default=False
    )

    policy = relationship(
        "Policy",
        back_populates="versions"
    )

    rules = relationship(
        "PolicyRule",
        back_populates="policy_version"
    )

    documents = relationship(
        "Document",
        back_populates="policy_version"
    )


# ================================================================
# POLICY DOCUMENT
# ================================================================

class Document(Base):
    __tablename__ = "documents"

    id = Column(
        Integer,
        primary_key=True
    )

    document_id = Column(
        String,
        nullable=False,
        unique=True
    )

    policy_version_db_id = Column(
        Integer,
        ForeignKey("policy_versions.id"),
        nullable=True
    )

    document_type = Column(
        String
    )

    source_url = Column(
        Text
    )

    sha256 = Column(
        String
    )

    hash_type = Column(
        String
    )

    original_file_available = Column(
        Boolean,
        default=False
    )

    page_count = Column(
        Integer
    )

    status = Column(
        String
    )

    notes = Column(
        Text
    )
    extracted_text_path = Column(
        String
    )

    policy_version = relationship(
        "PolicyVersion",
        back_populates="documents"
    )


# ================================================================
# POLICY RULE
# ================================================================

class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id = Column(
        Integer,
        primary_key=True
    )

    candidate_id = Column(
        String,
        nullable=False,
        unique=True
    )

    policy_version_db_id = Column(
        Integer,
        ForeignKey("policy_versions.id"),
        nullable=True
    )

    rule_type = Column(
        String,
        nullable=False
    )

    rule_name = Column(
        String
    )

    condition = Column(
        Text
    )

    value = Column(
        String
    )

    unit = Column(
        String
    )

    applies_to = Column(
        Text
    )

    exception = Column(
        Text
    )

    source_document = Column(
        String
    )

    source_page = Column(
        String
    )

    source_section = Column(
        String
    )

    source_text = Column(
        Text
    )

    extraction_method = Column(
        String
    )

    confidence = Column(
        String
    )

    review_status = Column(
        String,
        default="PENDING"
    )

    provenance = Column(
        String
    )

    policy_version = relationship(
        "PolicyVersion",
        back_populates="rules"
    )


# ================================================================
# REGULATORY RULE
# ================================================================

class RegulatoryRule(Base):
    __tablename__ = "regulatory_rules"

    id = Column(
        Integer,
        primary_key=True
    )

    regulation_id = Column(
        String,
        nullable=False,
        unique=True
    )

    topic = Column(
        String
    )

    requirement = Column(
        Text
    )

    value = Column(
        String
    )

    unit = Column(
        String
    )

    applicability = Column(
        Text
    )

    effective_date = Column(
        String
    )

    source_document = Column(
        String
    )

    source_page = Column(
        String
    )

    source_section = Column(
        String
    )

    source_text = Column(
        Text
    )

    source_url = Column(
        Text
    )

    provenance = Column(
        String
    )


# ================================================================
# PATIENT
# ================================================================

class Patient(Base):
    __tablename__ = "patients"

    id = Column(
        Integer,
        primary_key=True
    )

    synthetic_patient_id = Column(
        String,
        unique=True,
        nullable=False
    )

    age = Column(
        Integer
    )

    gender = Column(
        String
    )


# ================================================================
# CLAIM
# ================================================================

class Claim(Base):
    __tablename__ = "claims"

    id = Column(
        Integer,
        primary_key=True
    )

    # ------------------------------------------------------------
    # CLAIM IDENTIFICATION
    # ------------------------------------------------------------

    claim_ref = Column(
        String,
        unique=True,
        nullable=False
    )

    patient_id = Column(
        Integer,
        ForeignKey("patients.id")
    )

    policy_version_db_id = Column(
        Integer,
        ForeignKey("policy_versions.id"),
        nullable=False
    )

    patient_ref = Column(
        String
    )

    # ------------------------------------------------------------
    # POLICY DETAILS
    # ------------------------------------------------------------

    policy_start_date = Column(
        Date,
        nullable=False
    )

    policy_end_date = Column(
        Date
    )

    policy_cancelled_date = Column(
        Date
    )

    sum_insured = Column(
        Numeric
    )

    insured_age_at_entry = Column(
        Integer
    )

    # ------------------------------------------------------------
    # PREVIOUS INSURANCE / CONTINUITY
    # ------------------------------------------------------------

    previous_insurer_name = Column(
        String
    )

    previous_policy_start_date = Column(
        Date
    )

    previous_policy_end_date = Column(
        Date
    )

    continuous_coverage_since = Column(
        Date
    )

    # ------------------------------------------------------------
    # PATIENT DETAILS
    # ------------------------------------------------------------

    date_of_birth = Column(
        Date
    )

    gender = Column(
        String
    )

    # ------------------------------------------------------------
    # HOSPITAL DETAILS
    # ------------------------------------------------------------

    hospital_id = Column(
        String
    )

    hospital_type = Column(
        String
    )
    # NETWORK | NON_NETWORK

    hospital_registration_number = Column(
        String
    )

    ip_registration_number = Column(
        String
    )

    # ------------------------------------------------------------
    # HOSPITALISATION DETAILS
    # ------------------------------------------------------------

    admission_date = Column(
        Date
    )

    discharge_date = Column(
        Date
    )

    admission_type = Column(
        String
    )
    # EMERGENCY | PLANNED | DAY_CARE | MATERNITY

    claim_type = Column(
        String
    )
    # EMERGENCY | PLANNED

    admission_time = Column(
        String
    )

    discharge_time = Column(
        String
    )

    discharge_status = Column(
        String
    )
    # HOME | TRANSFERRED | DECEASED

    # ------------------------------------------------------------
    # ROOM / HOSPITAL CHARGES
    # ------------------------------------------------------------

    room_type = Column(
        String
    )

    room_rent_per_day = Column(
        Numeric
    )

    billed_amount = Column(
        Numeric
    )

    # ------------------------------------------------------------
    # DIAGNOSIS
    # ------------------------------------------------------------

    diagnosis_code = Column(
        String
    )

    diagnosis_description = Column(
        Text
    )

    additional_diagnoses = Column(
        Text
    )

    comorbidities = Column(
        Text
    )

    # ------------------------------------------------------------
    # PROCEDURE 1
    # ------------------------------------------------------------

    procedure_description = Column(
        Text
    )

    procedure_code = Column(
        String
    )

    # ------------------------------------------------------------
    # PROCEDURE 2
    # ------------------------------------------------------------

    procedure_2_description = Column(
        Text
    )

    procedure_2_code = Column(
        String
    )

    # ------------------------------------------------------------
    # PROCEDURE 3
    # ------------------------------------------------------------

    procedure_3_description = Column(
        Text
    )

    procedure_3_code = Column(
        String
    )

    # ------------------------------------------------------------
    # TREATMENT CATEGORY
    # ------------------------------------------------------------

    treatment_category = Column(
        String
    )

    category_billed_amount = Column(
        Numeric
    )

    # ------------------------------------------------------------
    # PREAUTHORIZATION
    # ------------------------------------------------------------

    preauth_status = Column(
        String,
        default="NONE"
    )
    # NONE | REQUESTED | APPROVED | DENIED

    preauth_number = Column(
        String
    )

    preauth_request_date = Column(
        Date
    )

    preauth_approval_date = Column(
        Date
    )

    # ------------------------------------------------------------
    # CLAIM NOTIFICATION / SUBMISSION
    # ------------------------------------------------------------

    notification_date = Column(
        Date
    )

    claim_filed_date = Column(
        Date
    )

    # ------------------------------------------------------------
    # INJURY / EXCLUSION INFORMATION
    # ------------------------------------------------------------

    injury_related = Column(
        Boolean
    )

    self_inflicted_injury = Column(
        Boolean
    )

    substance_abuse_related = Column(
        Boolean
    )

    substance_abuse_test_done = Column(
        Boolean
    )

    # ------------------------------------------------------------
    # MEDICO-LEGAL CASE
    # ------------------------------------------------------------

    medico_legal_case = Column(
        Boolean
    )

    police_reported = Column(
        Boolean
    )

    fir_number = Column(
        String
    )

    # ------------------------------------------------------------
    # MATERNITY
    # ------------------------------------------------------------

    delivery_date = Column(
        Date
    )

    gravida_status = Column(
        String
    )

    # ------------------------------------------------------------
    # DEDUCTIBLE
    # ------------------------------------------------------------

    deductible_opted = Column(
        Boolean,
        default=False
    )

    deductible_amount_opted = Column(
        Numeric
    )

    # ------------------------------------------------------------
 
        # DOCUMENTS
    # ------------------------------------------------------------

    documents_submitted = Column(
        Text
    )

    policy_document_received_date = Column(
        Date
    )

    additional_clinical_details = Column(
        Text
    )

    # ------------------------------------------------------------
    # PROVENANCE
    # ------------------------------------------------------------

    claim_provenance = Column(
        String,
        default="SYNTHETIC"
    )

    # ------------------------------------------------------------
    # TIMESTAMP
    # ------------------------------------------------------------

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

    # ------------------------------------------------------------
    # RELATIONSHIPS
    # ------------------------------------------------------------

    validation_results = relationship(
        "ValidationResult",
        back_populates="claim"
    )


# ================================================================
# VALIDATION RUN
# ================================================================

class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id = Column(
        Integer,
        primary_key=True
    )

    claim_id = Column(
        Integer,
        ForeignKey("claims.id")
    )

    run_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

    overall_result = Column(
        String
    )
    # SUBMISSION_READY
    # FIX_BEFORE_SUBMISSION
    # HUMAN_REVIEW_NEEDED


# ================================================================
# VALIDATION RESULT
# ================================================================

class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(
        Integer,
        primary_key=True
    )

    claim_id = Column(
        Integer,
        ForeignKey("claims.id")
    )

    validation_run_id = Column(
        Integer,
        ForeignKey("validation_runs.id")
    )

    rule_id = Column(
        String
    )

    category = Column(
        String
    )

    severity = Column(
        String
    )
    # PASS
    # WARNING
    # PARTIAL_DEDUCTION
    # FAIL

    reason = Column(
        Text
    )

    expected = Column(
        String
    )

    actual = Column(
        String
    )

    source_document = Column(
        String
    )

    source_page = Column(
        String
    )

    source_section = Column(
        String
    )

    provenance = Column(
        String
    )

    claim = relationship(
        "Claim",
        back_populates="validation_results"
    )


# ================================================================
# ICD-10
# ================================================================

class ICD10Code(Base):
    __tablename__ = "icd10_codes"

    id = Column(
        Integer,
        primary_key=True
    )

    code = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    description = Column(
        Text,
        nullable=False
    )

    source = Column(
        String,
        default="WHO"
    )

    release = Column(
        String,
        default="2019"
    )