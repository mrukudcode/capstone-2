"""
Import WHO ICD-10 diagnosis codes from JSON into SQLite.

Expected JSON format:

[
    {
        "code": "A00.0",
        "description": "Cholera due to Vibrio cholerae 01, biovar cholerae"
    },
    ...
]

Run from backend directory:

    python -m app.database.seed_icd10
"""

import json
import os
import sys

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)

from app.models.models import Base, ICD10Code
from app.database.db import engine, SessionLocal


# Your JSON is in Downloads
JSON_PATH = os.path.join(
    os.path.expanduser("~"),
    "Downloads",
    "icd10_who.json"
)


def run():

    if not os.path.exists(JSON_PATH):
        print(f"ERROR: File not found:")
        print(JSON_PATH)
        return

    print(f"Reading: {JSON_PATH}")

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Found {len(data)} ICD-10 records")

    # Make sure the table exists.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:

        # Clear existing ICD-10 records.
        db.query(ICD10Code).delete()

        count = 0

        for item in data:

            code = item.get("code")
            description = item.get("description")

            if not code or not description:
                continue

            record = ICD10Code(
                code=code.strip(),
                description=description.strip(),
                source="WHO",
                release="2019"
            )

            db.add(record)
            count += 1

        db.commit()

        print()
        print("===================================")
        print("ICD-10 IMPORT SUCCESSFUL")
        print("===================================")
        print(f"Imported: {count} codes")
        print("Source: WHO")
        print("Release: 2019")
        print("Database: claim_validator.db")
        print("===================================")

    except Exception as e:

        db.rollback()

        print("ERROR while importing ICD-10:")
        print(e)

    finally:
        db.close()


if __name__ == "__main__":
    run()