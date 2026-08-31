import sys

sys.path.insert(0, "backend")

from app.services.llm_claim_validator import validate_claim_against_rule


claim = {
    "claim_ref": "TEST-001",
    "sum_insured": 500000,
    "insured_age_at_entry": 65,
    "billed_amount": 100000,
    "room_rent_per_day": 7000,
    "treatment_category": "Hospitalization"
}


rule = {
    "rule_type": "ROOM_RENT_LIMIT",
    "rule_name": "Room Rent Limit for Sum Insured Rs. 5 Lakhs and Rs. 7.5 Lakhs",
    "condition": "Sum Insured = Rs. 5 Lakhs OR Sum Insured = Rs. 7.5 Lakhs",
    "value": "1",
    "unit": "% of Sum Insured per day",
    "applies_to": "Room Rent",
    "exception": "",
    "source_section": "Room Rent Criteria"
}


source_text = """
For Sum Insured of Rs. 5 Lakhs and Rs. 7.5 Lakhs,
Room Rent is limited to 1% of Sum Insured per day.
"""


result = validate_claim_against_rule(
    claim,
    rule,
    source_text
)

print("\nLLM VALIDATION RESULT")
print("=" * 80)

for key, value in result.items():
    print(f"{key}: {value}")