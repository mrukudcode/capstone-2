import sys
from datetime import date

sys.path.insert(0, "backend")

from app.database.db import SessionLocal
from app.models.models import Claim, PolicyVersion


db = SessionLocal()

try:
    # Find the Star Assure policy version that was seeded
    pv = (
        db.query(PolicyVersion)
        .filter(PolicyVersion.policy_version_id == "star_assure_2026_v1")
        .first()
    )

    if not pv:
        print("ERROR: star_assure_2026_v1 policy version not found.")
        raise SystemExit(1)

    # Avoid duplicate test claims
    existing = (
        db.query(Claim)
        .filter(Claim.claim_ref == "GROQ-RR-TEST-001")
        .first()
    )

    if existing:
        print("Claim already exists.")
        print("ID:", existing.id)
        print("Policy DB ID:", existing.policy_version_db_id)
        raise SystemExit(0)

    claim = Claim(
        claim_ref="GROQ-RR-TEST-001",

        policy_version_db_id=pv.id,

        sum_insured=500000,
        room_rent_per_day=7000,
        billed_amount=150000,

        insured_age_at_entry=60,

        policy_start_date=date(2022, 7, 12),
	admission_date=date(2026, 8, 18),
	discharge_date=date(2026, 8, 20),

        claim_type="PLANNED",
        preauth_status="APPROVED",
    )

    db.add(claim)
    db.commit()
    db.refresh(claim)

    print("=" * 80)
    print("GROQ TEST CLAIM CREATED")
    print("=" * 80)
    print("Claim ID:", claim.id)
    print("Claim ref:", claim.claim_ref)
    print("Policy DB ID:", claim.policy_version_db_id)
    print("Sum insured:", claim.sum_insured)
    print("Room rent/day:", claim.room_rent_per_day)
    print("Billed amount:", claim.billed_amount)

finally:
    db.close()