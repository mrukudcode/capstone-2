# Provenance-First Indian Health Insurance Claim Validator

A rule-based, deterministic, **pre-submission** claim sanity checker for
Indian health insurance claims. Every rule the system evaluates is
traceable to a real insurer or IRDAI document and page.

## What this is NOT
- Not an insurer claim-rejection prediction ML model.
- Not a medical diagnosis or medical-necessity adjudication system.
- Not connected to NHCX or any live insurer/TPA system.
- Not a guarantee of insurer payout — financial outputs (where
  implemented) are rule-based estimates only.
- Claims used for testing are **synthetic**, generated from real
  extracted policy rules, not real patient data.

## Status
See `docs/limitations.md` for an honest, itemized account of what is
real/working versus not-yet-implemented in this session. Short version:
the **dataset foundation and a real deterministic rule engine with a
working API are genuinely built and tested**; the frontend, RAG, FHIR
export, Docker packaging, and full test suite are not yet built.

## Repository layout
```
data/
  raw/policies/{star_health,hdfc_ergo}/   - extracted policy text, page-preserved
  raw/regulatory/irdai/                   - extracted IRDAI circular text
  structured/                             - CSVs: source_documents, policy_inventory, policy_rule_candidates
backend/
  app/models/                             - SQLAlchemy models (SQLite this session; Postgres-ready)
  app/database/seed.py                    - loads the real CSVs into the DB, no fabricated rows
  app/rules/waiting_period.py, engine.py  - the only implemented deterministic rule evaluator
  app/main.py                             - FastAPI app
scripts/validate_dataset.py               - dataset integrity validator (0 errors, 5 documented warnings)
docs/
  HDFC_ERGO_UIN_REVIEW.md                 - documented, unresolved UIN conflict for HDFC Optima Secure
  limitations.md                          - full honest gap list
```

## Running the backend
```bash
cd backend
pip install sqlalchemy fastapi "uvicorn[standard]" pydantic httpx
python -m app.database.seed
uvicorn app.main:app --reload
```

## Key design guarantee, verified in this session
A claim's rule evaluation is scoped **only** to its own
`policy_version_id`. This was tested directly: a synthetic HDFC 2026
claim run against the seeded database evaluated zero Star Health rules
(correct isolation), and also zero HDFC rules (correct, because the
HDFC 2026 rules are flagged `NEEDS_REVIEW` pending the UIN conflict
resolution in `docs/HDFC_ERGO_UIN_REVIEW.md`, and the engine only
auto-evaluates `PENDING`/`APPROVED` rules).

## Data provenance categories
- **REAL**: original insurer/regulatory document text (extracted, not
  original PDF bytes — see limitations.md for why).
- **DERIVED**: rules extracted from those documents (`policy_rule_candidates.csv`).
- **SYNTHETIC**: claims created to exercise the rule engine.
- Nothing in this dataset is fabricated to "fill gaps" — missing values
  are recorded as `NOT_SPECIFIED_IN_SOURCE` or `NOT_FOUND_IN_SOURCE`.
