import sys
sys.path.insert(0, "backend")

from app.database.db import SessionLocal
from app.models.models import PolicyRule
from app.services.llm_claim_validator import validate_claim_against_rule


db = SessionLocal()

rule = (
    db.query(PolicyRule)
    .filter(PolicyRule.rule_type == "ROOM_RENT_LIMIT")
    .first()
)

if rule is None:
    print("ERROR: No ROOM_RENT_LIMIT rule found in database.")
    db.close()
    raise SystemExit(1)


claim_data = {
    "sum_insured": 500000,
    "room_rent_per_day": 7000,
    "room_type": "Private Room",
    "admission_date": "2026-08-20",
    "claim_type": "PLANNED"
}


rule_data = {
    "rule_id": rule.candidate_id,
    "rule_type": rule.rule_type,
    "rule_name": rule.rule_name,
    "condition": rule.condition,
    "value": rule.value,
    "unit": rule.unit,
    "applies_to": rule.applies_to,
    "exception": rule.exception,
}


result = validate_claim_against_rule(
    claim_data=claim_data,
    rule=rule_data,
    source_text=rule.source_text or ""
)


print()
print("DB RULE + GROQ VALIDATION")
print("=" * 80)

for key, value in result.items():
    print(f"{key}: {value}")


db.close()