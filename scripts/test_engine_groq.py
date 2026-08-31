import sys

sys.path.insert(0, "backend")

from app.database.db import SessionLocal
from app.models.models import Claim, PolicyRule
from app.rules.engine import validate_claim


db = SessionLocal()

# ================================================================
# SELECT THE EXACT CLAIM TO TEST
# ================================================================

claim = (
    db.query(Claim)
    .filter(Claim.claim_ref == "GROQ-RR-TEST-001")
    .first()
)

if not claim:
    print("CLAIM GROQ-RR-TEST-001 NOT FOUND")
    db.close()
    raise SystemExit(1)


# ================================================================
# PRINT CLAIM INPUT
# ================================================================

print("=" * 80)
print("TESTING HYBRID GROQ + RULE ENGINE")
print("=" * 80)

print("Claim:", claim.claim_ref)
print("Policy DB ID:", claim.policy_version_db_id)

print()
print("CLAIM INPUT")
print("=" * 80)

print("Sum insured:", claim.sum_insured)
print("Room rent/day:", claim.room_rent_per_day)
print("Billed amount:", claim.billed_amount)
print("Age at entry:", claim.insured_age_at_entry)
print("Diagnosis:", claim.diagnosis_description)
print("Diagnosis code:", claim.diagnosis_code)
print("Admission:", claim.admission_date)
print("Discharge:", claim.discharge_date)
print("Policy start:", claim.policy_start_date)
print("Policy end:", claim.policy_end_date)
print("Treatment category:", claim.treatment_category)
print("Category billed amount:", claim.category_billed_amount)
print("Deductible opted:", claim.deductible_opted)
print("Deductible amount:", claim.deductible_amount_opted)
print("Claim type:", claim.claim_type)
print("Preauth status:", claim.preauth_status)


# ================================================================
# VERIFY RULES BELONG TO THIS POLICY
# ================================================================

print()
print("POLICY RULES")
print("=" * 80)

policy_rules = (
    db.query(PolicyRule)
    .filter(
        PolicyRule.policy_version_db_id
        == claim.policy_version_db_id
    )
    .all()
)

print("Total rules for this policy:", len(policy_rules))

for rule in policy_rules:
    print(
        f"{rule.candidate_id} | "
        f"{rule.rule_type} | "
        f"{rule.rule_name} | "
        f"value={rule.value} | "
        f"unit={rule.unit} | "
        f"status={rule.review_status}"
    )


# ================================================================
# SPECIFICALLY CHECK ROOM RENT RULE
# ================================================================

room_rent_rule = (
    db.query(PolicyRule)
    .filter(
        PolicyRule.policy_version_db_id
        == claim.policy_version_db_id,
        PolicyRule.rule_type
        == "ROOM_RENT_LIMIT"
    )
    .first()
)

print()
print("ROOM RENT RULE CHECK")
print("=" * 80)

if room_rent_rule:

    print("Rule found:", room_rent_rule.candidate_id)
    print("Rule type:", room_rent_rule.rule_type)
    print("Rule name:", room_rent_rule.rule_name)
    print("Value:", room_rent_rule.value)
    print("Unit:", room_rent_rule.unit)
    print("Condition:", room_rent_rule.condition)
    print("Applies to:", room_rent_rule.applies_to)
    print("Status:", room_rent_rule.review_status)

else:

    print(
        "WARNING: No ROOM_RENT_LIMIT rule exists "
        "for this claim's policy version."
    )


# ================================================================
# RUN HYBRID VALIDATION ENGINE
# ================================================================

print()
print("RUNNING VALIDATION")
print("=" * 80)

run, results, financials = validate_claim(
    db,
    claim
)


# ================================================================
# OVERALL RESULT
# ================================================================

print()
print("OVERALL RESULT")
print("=" * 80)

print(run.overall_result)


# ================================================================
# VALIDATION RESULTS
# ================================================================

print()
print("VALIDATION RESULTS")
print("=" * 80)

if not results:

    print("NO VALIDATION RESULTS FOUND")

else:

    for r in results:

        print()
        print("Rule:", r["rule_id"])
        print("Category:", r["category"])
        print("Severity:", r["severity"])
        print("Reason:", r["reason"])
        print("Expected:", r["expected"])
        print("Actual:", r["actual"])
        print("Provenance:", r["provenance"])


# ================================================================
# FINANCIAL RESULTS
# ================================================================

print()
print("FINANCIALS")
print("=" * 80)

for key, value in financials.items():
    print(f"{key}: {value}")


# ================================================================
# ROOM RENT SUMMARY
# ================================================================

print()
print("ROOM RENT SUMMARY")
print("=" * 80)

if (
    claim.sum_insured is not None
    and claim.room_rent_per_day is not None
):

    print("Sum insured:", claim.sum_insured)
    print("Actual room rent/day:", claim.room_rent_per_day)

    if room_rent_rule:

        try:
            percentage = float(room_rent_rule.value)

            allowed_room_rent = (
                float(claim.sum_insured)
                * percentage
                / 100
            )

            print(
                f"Policy room-rent limit: "
                f"{percentage}% of Sum Insured/day"
            )

            print(
                "Calculated allowed room rent/day:",
                allowed_room_rent
            )

            if float(claim.room_rent_per_day) <= allowed_room_rent:

                print("Room rent status: PASS")

            else:

                print("Room rent status: LIMIT EXCEEDED")

                proportion = (
                    allowed_room_rent
                    / float(claim.room_rent_per_day)
                )

                print(
                    "Admissible room-rent proportion:",
                    round(proportion, 4)
                )

        except (TypeError, ValueError):

            print(
                "Could not calculate room-rent limit "
                "from rule value."
            )

    else:

        print(
            "Room-rent calculation skipped because "
            "no ROOM_RENT_LIMIT rule exists for this policy."
        )

else:

    print(
        "Room-rent calculation cannot be performed because "
        "sum_insured or room_rent_per_day is missing."
    )


# ================================================================
# CLOSE DATABASE
# ================================================================

db.close()