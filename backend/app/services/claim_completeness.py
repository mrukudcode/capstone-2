"""
Claim completeness analysis.

Determines which claim fields are required before a policy rule
can be evaluated and tells the user where/how to provide them.
"""

from typing import Any


FIELD_LABELS = {
    "procedure_code": "Procedure code",
    "procedure_description": "Procedure description",
    "diagnosis_code": "Diagnosis code",
    "diagnosis_description": "Diagnosis description",
    "admission_date": "Admission date",
    "discharge_date": "Discharge date",
    "claim_filed_date": "Claim filed date",
    "notification_date": "Notification date",
    "claim_type": "Claim type",
    "sum_insured": "Sum insured",
    "insured_age_at_entry": "Insured age at policy entry",
    "billed_amount": "Total billed amount",
    "room_type": "Room type",
    "room_rent_per_day": "Room rent per day",
    "treatment_category": "Treatment category",
    "category_billed_amount": "Category billed amount",
    "preauth_status": "Pre-authorization status",
    "preauth_request_date": "Pre-authorization request date",
    "deductible_opted": "Deductible opted",
    "deductible_amount_opted": "Deductible amount opted",
    "documents_submitted": "Documents submitted",
    "injury_related": "Injury related",
    "self_inflicted_injury": "Self-inflicted injury",
    "substance_abuse_related": "Substance abuse related",
    "substance_abuse_test_done": "Substance abuse test done",
    "medico_legal_case": "Medico-legal case",
    "police_reported": "Police reported",
    "fir_number": "FIR number",
    "delivery_date": "Delivery date",
    "gravida_status": "Pregnancy/gravida status",
}


FIELD_LOCATIONS = {
    "procedure_code": "Claim Details → Treatment / Procedure",
    "procedure_description": "Claim Details → Treatment / Procedure",
    "diagnosis_code": "Claim Details → Diagnosis",
    "diagnosis_description": "Claim Details → Diagnosis",
    "admission_date": "Hospitalization Details → Admission",
    "discharge_date": "Hospitalization Details → Discharge",
    "claim_filed_date": "Claim Details → Claim Submission",
    "notification_date": "Claim Details → Claim Notification",
    "claim_type": "Claim Details → Claim Type",
    "sum_insured": "Policy Details → Sum Insured",
    "insured_age_at_entry": "Policy Details → Insured Age at Entry",
    "billed_amount": "Financial Details → Total Billed Amount",
    "room_type": "Hospitalization Details → Room",
    "room_rent_per_day": "Hospitalization Details → Room Rent",
    "treatment_category": "Treatment Details → Treatment Category",
    "category_billed_amount": "Financial Details → Category Amount",
    "preauth_status": "Pre-authorization Details → Status",
    "preauth_request_date": "Pre-authorization Details → Request Date",
    "deductible_opted": "Policy Details → Deductible",
    "deductible_amount_opted": "Policy Details → Deductible Amount",
    "documents_submitted": "Documents → Submitted Documents",
    "injury_related": "Clinical Details → Injury",
    "self_inflicted_injury": "Clinical Details → Self-inflicted Injury",
    "substance_abuse_related": "Clinical Details → Substance Abuse",
    "substance_abuse_test_done": "Clinical Details → Substance Abuse Test",
    "medico_legal_case": "Clinical / Legal Details → Medico-legal Case",
    "police_reported": "Clinical / Legal Details → Police Report",
    "fir_number": "Clinical / Legal Details → FIR Number",
    "delivery_date": "Clinical Details → Delivery Date",
    "gravida_status": "Clinical Details → Pregnancy Details",
}


def _value(claim: Any, field: str):
    if isinstance(claim, dict):
        return claim.get(field)

    return getattr(claim, field, None)


def missing_fields(claim, fields):
    """
    Return structured information about missing fields.
    """

    missing = []

    for field in fields:
        value = _value(claim, field)

        if value is None or value == "":
            missing.append(
                {
                    "field": field,
                    "label": FIELD_LABELS.get(field, field.replace("_", " ").title()),
                    "where_to_provide": FIELD_LOCATIONS.get(
                        field,
                        "Claim Details"
                    ),
                }
            )

    return missing


def requirement(
    rule_id,
    rule_name,
    fields,
    reason,
):
    """
    Create a missing-data requirement for a rule.
    """

    return {
        "rule_id": rule_id,
        "rule_name": rule_name,
        "required_fields": fields,
        "reason": reason,
    }


def analyze_claim_completeness(claim, active_rules):
    """
    Determine whether important policy rules have enough claim data
    to be evaluated.

    This does NOT declare a claim invalid.
    It only identifies information that is required to evaluate rules.
    """

    requirements = []

    for rule in active_rules:

        rule_type = (rule.rule_type or "").upper()

        if rule_type == "CLAIM_FILING_DEADLINE":
            requirements.append(
                requirement(
                    rule.id,
                    rule.rule_name,
                    [
                        "claim_filed_date",
                        "discharge_date",
                    ],
                    "The filing deadline requires the claim filing date and discharge date.",
                )
            )

        elif rule_type == "CLAIM_NOTIFICATION_DEADLINE":

            # Only relevant for emergency claims.
            if (getattr(claim, "claim_type", "") or "").upper() == "EMERGENCY":
                requirements.append(
                    requirement(
                        rule.id,
                        rule.rule_name,
                        [
                            "notification_date",
                            "admission_date",
                        ],
                        "Emergency notification deadline requires notification and admission dates.",
                    )
                )

        elif rule_type == "ROOM_RENT_LIMIT":
            requirements.append(
                requirement(
                    rule.id,
                    rule.rule_name,
                    [
                        "sum_insured",
                        "room_rent_per_day",
                    ],
                    "Room-rent eligibility requires the sum insured and actual room rent.",
                )
            )

        elif rule_type == "COPAY":
            requirements.append(
                requirement(
                    rule.id,
                    rule.rule_name,
                    [
                        "insured_age_at_entry",
                        "billed_amount",
                    ],
                    "Co-payment calculation requires insured age at entry and billed amount.",
                )
            )

        elif rule_type == "DEDUCTIBLE":
            if getattr(claim, "deductible_opted", False):
                requirements.append(
                    requirement(
                        rule.id,
                        rule.rule_name,
                        [
                            "deductible_amount_opted",
                            "billed_amount",
                        ],
                        "Deductible calculation requires the opted deductible amount and billed amount.",
                    )
                )

        elif rule_type == "SUBLIMIT":
            requirements.append(
                requirement(
                    rule.id,
                    rule.rule_name,
                    [
                        "treatment_category",
                        "category_billed_amount",
                        "sum_insured",
                    ],
                    "Sub-limit calculation requires the treatment category, category amount and sum insured.",
                )
            )

        elif rule_type == "PREAUTH":
            if (getattr(claim, "claim_type", "") or "").upper() == "PLANNED":
                requirements.append(
                    requirement(
                        rule.id,
                        rule.rule_name,
                        [
                            "preauth_request_date",
                            "admission_date",
                        ],
                        "Planned-treatment pre-authorization requires the request and admission dates.",
                    )
                )

        elif rule_type == "DOCUMENTATION":
            requirements.append(
                requirement(
                    rule.id,
                    rule.rule_name,
                    [
                        "documents_submitted",
                        "billed_amount",
                    ],
                    "Documentation rules require submitted-document information and billed amount.",
                )
            )

    missing = []

    for req in requirements:
        fields_missing = missing_fields(
            claim,
            req["required_fields"]
        )

        if fields_missing:
            missing.append(
                {
                    "rule_id": req["rule_id"],
                    "rule_name": req["rule_name"],
                    "reason": req["reason"],
                    "missing_fields": fields_missing,
                }
            )

    return missing