"""
RAG question-answering endpoints.

POST /claims/{claim_id}/questions  (mandatory, per project requirement)
POST /policies/{policy_version_id}/questions  (optional convenience route)

The claim-scoped endpoint derives policy_version_id from the claim
itself in the database -- the client can never override it, preventing
a caller from asking a Star Health claim's question against HDFC's
documents.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database.db import get_db
from app.models.models import Claim, PolicyVersion
from app.rag.service import answer_question

router = APIRouter()


class QuestionIn(BaseModel):
    question: str


@router.post("/claims/{claim_id}/questions")
def ask_claim_question(claim_id: int, body: QuestionIn, db: Session = Depends(get_db)):
    claim = db.query(Claim).get(claim_id)
    if not claim:
        raise HTTPException(404, "claim not found")
    pv = db.query(PolicyVersion).get(claim.policy_version_db_id)
    if not pv:
        raise HTTPException(500, "claim has no associated policy version")

    result = answer_question(body.question, pv.policy_version_id)
    return {
        "claim_id": claim_id,
        "policy_version_id": pv.policy_version_id,
        "question": body.question,
        **result,
    }


@router.post("/policies/{policy_version_id}/questions")
def ask_policy_question(policy_version_id: str, body: QuestionIn, db: Session = Depends(get_db)):
    pv = db.query(PolicyVersion).filter_by(policy_version_id=policy_version_id).first()
    if not pv:
        raise HTTPException(404, f"Unknown policy_version_id: {policy_version_id}")

    result = answer_question(body.question, policy_version_id)
    return {
        "policy_version_id": policy_version_id,
        "question": body.question,
        **result,
    }
