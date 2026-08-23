# Limitations (Honest, As of This Session)

## Environment constraints
- This session's tools cannot retrieve raw PDF bytes. `web_fetch` returns
  extracted text even when raw-bytes mode is requested, and `bash_tool`'s
  network egress is restricted to package-registry domains (no
  `hdfcergo.com`, `starhealth.in`, `irdai.gov.in`, etc.). Consequently
  **every** source document in this dataset has `hash_type=EXTRACTED_TEXT`
  and `original_file_available=false` — never `ORIGINAL_FILE`. This is
  recorded honestly per-document in `source_documents.csv`, exactly as the
  project's own fallback rule anticipates.
- `irdai.gov.in` blocks automated access (`ROBOTS_DISALLOWED`) in this
  environment. The Master Circular text used here comes from a
  full-text, verbatim third-party republication that matches the
  official reference number, date, and signatory exactly — but it is not
  a direct fetch from irdai.gov.in itself. Re-verification against the
  primary IRDAI URL is recommended in a session with browser access.

## Dataset scope actually completed this session
- 2 insurers, 2 products, 4 policy_version rows (Star Assure 2026; HDFC
  Optima Secure 2026 under two conflicting UINs; HDFC Optima Secure 2021
  historical).
- 5 source documents (Star Assure CIS 2026; HDFC Optima Secure Policy
  Wording 2026; HDFC Optima Secure CIS 2026; HDFC Optima Secure combined
  CIS+PW 2021; IRDAI Master Circular 2024).
- 59 rule candidates (49 insurer-sourced, 10 regulatory), all
  `review_status=PENDING` or `NEEDS_REVIEW` — none auto-approved.
- Star Health's full **Policy Wording** PDF (as opposed to the CIS) was
  located (`Policy_Star_Health_Assure_Insurance_Policy_V_9_c53663e68a.pdf`)
  but **not yet ingested** — only the CIS was extracted. The CIS is itself
  an official, page-cited insurer document, but it is a summary, so some
  rule categories (e.g. exact sub-limit rupee figures beyond what's in
  the CIS tables) are less exhaustively captured for Star than for HDFC.
- HDFC's Policy Wording extraction covers pages ~1–42 of 60; Section E
  (claims procedure) and Annexures A–C were not pulled in this pass.
- ICICI Lombard / Care Health (the optional third/fourth insurers) were
  **not attempted** in this session due to time constraints — this is an
  honest gap, not a silent omission.

## Backend/API scope actually completed this session
- Real SQLite database (documented substitution for Postgres — same
  SQLAlchemy ORM, connection string swap only) seeded from the actual
  CSVs above, with zero fabricated rows.
- A genuinely deterministic waiting-period rule engine
  (`backend/app/rules/waiting_period.py` + `engine.py`), verified against
  real boundary cases (23 vs 25 months against Star's actual 24-month
  specified-disease wait) via FastAPI's TestClient, with a passing
  cross-policy-isolation check (an HDFC claim retrieves zero Star rules,
  and — because the HDFC 2026 rules are flagged NEEDS_REVIEW — zero HDFC
  rules either, which is correct given the unresolved UIN conflict).
- A minimal FastAPI surface: `/api/health`, `/api/policies`,
  `/api/policies/{policy_version_id}/rules`, `POST /api/claims`,
  `GET /api/claims/{id}`, `POST /api/claims/{id}/validate`.

## Update (this session, continued)
All of the following are now REAL and tested, not stubs:
`exclusion.py` (keyword-overlap, WARNING-capped), `room_rent.py`,
`sublimit.py`, `copay.py`, `deductible.py`, `deadline.py` (filing +
notification), `preauth.py` (policyholder-side lead time only),
`documentation.py`, plus honest limited/empty modules `eligibility.py`
(0 rules exist) and `policy_status.py` (derived logic, not tied to a
specific extracted rule — documented in its own docstring).
`services/financial_calculator.py` is real, with a documented,
non-arbitrary calculation-order decision (see `docs/rule_engine.md`).
18/18 pytest tests pass; 28/28 synthetic claims match expected severity
end-to-end. One real bug (`sublimit.py` percentage-parsing) was found and
fixed by this test suite. See `docs/rule_engine.md` and
`docs/evaluation_report.md` for full detail.

## NOT implemented this session (explicitly, not silently)
- RAG policy Q&A (embeddings, vector store, policy-scoped retrieval).
- FHIR/NHCX-shaped Claim/ClaimResponse export.
- React/Vite frontend and all dashboard pages.
- Docker Compose, Dockerfiles, `.env.example`.
- Audit logging table/middleware.
- `regulatory_rules.csv` as a standalone file (the 10 regulatory rules
  currently live only inside `policy_rule_candidates.csv` with
  `provenance=REGULATORY_DOCUMENT`, and are separately seeded into their
  own `regulatory_rules` DB table — but the standalone CSV file itself
  was not written).

## Why this list exists
The instructions explicitly prohibit fabricated completion claims,
mocked dashboard data, and fake API responses. Given the genuine time
budget of a single session, building all nineteen requested MVP
components to a real, tested standard was not achievable without cutting
exactly the corners this document lists. What **was** built is real:
real extracted policy text with page citations, a real seeded database,
and a real deterministic rule engine that correctly fails/passes/
isolates rules end-to-end.
