from fastapi import APIRouter, Query
from sqlalchemy import or_

from app.database.db import SessionLocal
from app.models.models import ICD10Code


router = APIRouter(
    prefix="/api/icd10",
    tags=["ICD-10"],
)


@router.get("/search")
async def search_icd10(
    q: str = Query(
        ...,
        min_length=2,
        description="Disease, condition, ICD-10 code, or diagnosis to search",
    )
):
    """
    Search the locally imported WHO ICD-10 2019 database.

    Example:
        /api/icd10/search?q=diabetes

    The frontend can then let the user select one exact diagnosis
    from the returned dropdown.
    """

    query = q.strip()

    if not query:
        return {
            "query": q,
            "classification": "ICD-10",
            "release": "2019",
            "language": "en",
            "source": "WHO",
            "results": [],
        }

    db = SessionLocal()

    try:
        # Search both ICD code and diagnosis description.
        #
        # Example:
        #   diabetes
        #   hypertension
        #   pneumonia
        #   E11.9
        #
        # SQLite LIKE is case-insensitive for normal ASCII text,
        # so this works for common diagnosis searches.

        search_pattern = f"%{query}%"

        records = (
            db.query(ICD10Code)
            .filter(
                or_(
                    ICD10Code.code.ilike(search_pattern),
                    ICD10Code.description.ilike(search_pattern),
                )
            )
            .order_by(ICD10Code.code)
            .limit(50)
            .all()
        )

        results = []

        for item in records:
            results.append(
                {
                    "id": item.id,
                    "code": item.code,
                    "title": item.description,
                }
            )

        return {
            "query": q,
            "classification": "ICD-10",
            "release": "2019",
            "language": "en",
            "source": "WHO",
            "results": results,
        }

    finally:
        db.close()