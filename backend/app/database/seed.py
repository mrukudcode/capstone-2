"""
Seed the database from the real, provenance-tracked dataset CSVs produced in
Phase A (data/structured/*.csv). Does NOT invent any rule, UIN, or document
that isn't in those CSVs. Run: python -m app.database.seed
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.models.models import (
    Base, Insurer, Policy, PolicyVersion, Document, PolicyRule, RegulatoryRule,
)
from app.database.db import engine, SessionLocal

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "structured",
)


def load_csv(name):
    path = os.path.join(DATA_DIR, name)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    insurers = {}
    policies = {}
    policy_versions = {}

    inv_rows = load_csv("policy_inventory.csv")
    for row in inv_rows:
        insurer_name = row["insurer"]
        if insurer_name not in insurers:
            ins = Insurer(name=insurer_name)
            db.add(ins)
            db.flush()
            insurers[insurer_name] = ins

        pol_key = (insurer_name, row["product"])
        if pol_key not in policies:
            pol = Policy(insurer_id=insurers[insurer_name].id, product_name=row["product"])
            db.add(pol)
            db.flush()
            policies[pol_key] = pol

        pv = PolicyVersion(
            policy_id=policies[pol_key].id,
            policy_version_id=row["policy_version_id"],
            uin=row["uin"],
            status=row["status"],
            uin_conflict_flag=(row["uin_conflict_flag"].strip().lower() == "true"),
        )
        db.add(pv)
        db.flush()
        policy_versions[row["policy_version_id"]] = pv

    db.commit()

    doc_rows = load_csv("source_documents.csv")
    # Map each document_id to its policy_version_id based on which policy
    # version's rules actually cite it (derived from policy_rule_candidates.csv,
    # not invented) -- this was previously left as None for every document,
    # which would have made RAG chunk-to-policy-version scoping incorrect.
    rule_rows_for_mapping = load_csv("policy_rule_candidates.csv")
    doc_to_pv = {}
    for r in rule_rows_for_mapping:
        doc = r["source_document"]
        pv_id = r["policy_version"]
        if doc and doc != "NOT_SPECIFIED_IN_SOURCE" and pv_id in policy_versions:
            doc_to_pv.setdefault(doc, set()).add(pv_id)

    for row in doc_rows:
        pv_db_id = None
        mapped_versions = doc_to_pv.get(row["document_id"])
        if mapped_versions:
            # A document should map to exactly one policy version in this
            # dataset; if it maps to more than one, leave unset rather than
            # guess (this hasn't occurred in the current 59-row dataset).
            if len(mapped_versions) == 1:
                only_pv_id = next(iter(mapped_versions))
                pv_db_id = policy_versions[only_pv_id].id
        doc = Document(
            document_id=row["document_id"],
            policy_version_db_id=pv_db_id,
            document_type=row["document_type"],
            source_url=row["source_url"],
            sha256=row["sha256"],
            hash_type=row["hash_type"],
            original_file_available=(row["hash_type"] == "ORIGINAL_FILE"),
            page_count=(int(row["page_count"]) if row["page_count"].isdigit() else None),
            status=row["status"],
            notes=row["notes"],
        )
        db.add(doc)
    db.commit()

    rule_rows = load_csv("policy_rule_candidates.csv")
    n_policy_rules = 0
    n_regulatory_rules = 0
    for row in rule_rows:
        if row["provenance"] == "REGULATORY_DOCUMENT":
            rr = RegulatoryRule(
                regulation_id=row["candidate_id"],
                topic=row["rule_type"],
                requirement=row["rule_name"],
                value=row["value"],
                unit=row["unit"],
                applicability=row["applies_to"],
                effective_date="2024-05-29",
                source_document=row["source_document"],
                source_page=row["source_page"],
                source_section=row["source_section"],
                source_text=row["source_text"],
                source_url="https://irdai.gov.in/document-detail?documentId=4942918",
                provenance=row["provenance"],
            )
            db.add(rr)
            n_regulatory_rules += 1
        else:
            pv = policy_versions.get(row["policy_version"])
            pr = PolicyRule(
                candidate_id=row["candidate_id"],
                policy_version_db_id=(pv.id if pv else None),
                rule_type=row["rule_type"],
                rule_name=row["rule_name"],
                condition=row["condition"],
                value=row["value"],
                unit=row["unit"],
                applies_to=row["applies_to"],
                exception=row["exception"],
                source_document=row["source_document"],
                source_page=row["source_page"],
                source_section=row["source_section"],
                source_text=row["source_text"],
                extraction_method=row["extraction_method"],
                confidence=row["confidence"],
                review_status=row["review_status"],
                provenance=row["provenance"],
            )
            db.add(pr)
            n_policy_rules += 1
    db.commit()

    print(f"Seeded: {len(insurers)} insurers, {len(policies)} products, "
          f"{len(policy_versions)} policy versions, {len(doc_rows)} documents, "
          f"{n_policy_rules} policy rules, {n_regulatory_rules} regulatory rules.")
    db.close()


if __name__ == "__main__":
    run()
