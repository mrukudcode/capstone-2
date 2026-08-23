#!/usr/bin/env python3
"""
Build the RAG chunk index from the REAL extracted-text documents already
in data/raw/. Reads the actual document-to-policy-version mapping from the
seeded database (backend/claim_validator.db) so the mapping is derived
from the same source of truth the rule engine uses, not re-invented here.

Run: python scripts/build_rag_index.py
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "backend"))

from app.database.db import SessionLocal
from app.models.models import Document, PolicyVersion
from app.rag.chunking import build_all_chunks, DOCUMENT_TEXT_FILES
from app.rag.embeddings import build_index


def main():
    db = SessionLocal()
    doc_to_pv = {}
    doc_to_prov = {}
    for doc in db.query(Document).all():
        if doc.document_id not in DOCUMENT_TEXT_FILES:
            continue
        pv_id = None
        if doc.policy_version_db_id:
            pv = db.query(PolicyVersion).get(doc.policy_version_db_id)
            pv_id = pv.policy_version_id if pv else None
        doc_to_pv[doc.document_id] = pv_id
        # IRDAI circular has no product -> regulatory; everything else insurer.
        doc_to_prov[doc.document_id] = (
            "REGULATORY_DOCUMENT" if pv_id is None else "INSURER_DOCUMENT"
        )
    db.close()

    missing = set(DOCUMENT_TEXT_FILES) - set(doc_to_pv)
    if missing:
        print(f"WARNING: documents in DOCUMENT_TEXT_FILES but not found in DB: {missing}")

    chunks = build_all_chunks(doc_to_pv, doc_to_prov)
    build_index(chunks)

    print(f"Built RAG index: {len(chunks)} chunks from {len(DOCUMENT_TEXT_FILES)} documents.")
    by_pv = {}
    for c in chunks:
        key = c.policy_version_id or "(regulatory, unscoped)"
        by_pv[key] = by_pv.get(key, 0) + 1
    for pv_id, count in by_pv.items():
        print(f"  {pv_id}: {count} chunks")


if __name__ == "__main__":
    main()
