# Dataset Summary (Mentor-Facing)

All figures calculated from the actual repository files as of this
session — see `docs/dataset_documentation.md` §18 for the source
validation run these tables are built from.

## A. Insurers, products, policy versions

| Insurer | Product | Policy Version ID | UIN | Effective Date | Source Document | Verification Status |
|---|---|---|---|---|---|---|
| Star Health and Allied Insurance Co Ltd | Star Health Assure Insurance Policy | `star_assure_2026_v1` | SHAHLIP26048V032526 | NOT_SPECIFIED_IN_SOURCE | STAR_ASSURE_2026_CIS | ✅ Verified, no conflicts |
| HDFC ERGO General Insurance Company Limited | my:Optima Secure | `hdfc_optima_secure_2026_v1` | HDFHLIP26058V082526 | 2026-04-02 | HDFC_OPTIMA_SECURE_2026_POLICY_WORDING | ⚠️ UIN CONFLICT — needs review |
| HDFC ERGO General Insurance Company Limited | my:Optima Secure | `hdfc_optima_secure_2026_v1_CIS_UIN` | HDFHLIP25041V062425 | NOT_SPECIFIED_IN_SOURCE | HDFC_OPTIMA_SECURE_2026_CIS | ⚠️ UIN CONFLICT — needs review |
| HDFC ERGO General Insurance Company Limited | my:Optima Secure | `hdfc_optima_secure_2021_v1` | HDFHLIP21016V012122 | 2021-08-19 | HDFC_OPTIMA_SECURE_2021_HISTORICAL | ✅ Verified historical, isolated from 2026 rules |

## B. Rule categories

| Category | # of Rules | Insurers/Products | Verification Status |
|---|---|---|---|
| INITIAL_WAITING_PERIOD | 3 | Star Assure 2026, HDFC 2021 | ✅ Evaluator implemented + tested |
| SPECIFIED_DISEASE_WAITING_PERIOD | 3 | Star Assure 2026, HDFC 2026, HDFC 2021 | ✅ Evaluator implemented + tested |
| PED_WAITING_PERIOD | 4 | Star Assure 2026 (x2), HDFC 2026, HDFC 2021 | ✅ Evaluator implemented + tested |
| ROOM_RENT_LIMIT | 2 | Star Assure 2026, HDFC 2026 | ✅ Evaluator implemented + tested (1 band only) |
| SUB_LIMIT | 4 | Star Assure 2026 (x2), HDFC 2026, HDFC 2021 | ✅ Evaluator implemented + tested |
| CO_PAYMENT | 1 | Star Assure 2026 | ✅ Evaluator implemented + tested |
| DEDUCTIBLE | 2 | Star Assure 2026, HDFC 2026 | ✅ Evaluator implemented + tested |
| CLAIM_FILING_DEADLINE | 5 | Star Assure 2026 (x2), HDFC 2026, HDFC 2021 (x2) | ✅ Evaluator implemented + tested |
| CLAIM_NOTIFICATION_DEADLINE | 2 | Star Assure 2026, HDFC 2021 | ✅ Evaluator implemented + tested |
| PREAUTH_REQUIREMENT | 5 | Star Assure 2026 (x3), IRDAI (x2) | ⚠️ Only 1 of 5 evaluable from claim data (rest are insurer-side TAT) |
| EXCLUSION | 3 | Star Assure 2026 (x2), HDFC 2026 | ⚠️ Keyword-overlap only, capped at WARNING |
| NON_COVERED_TREATMENT | 2 | Star Assure 2026, HDFC 2026 | ⚠️ Keyword-overlap only, capped at WARNING |
| POLICY_VERSION_RULE | 16 | All 4 policy versions + IRDAI | ℹ️ Informational (free-look, moratorium, portability, etc.) — not independently evaluated by the rule engine |
| POLICY_INACTIVE | 3 | HDFC 2021, IRDAI | ⚠️ Derived business logic only, not tied to specific extracted clause |
| POLICY_EXPIRED | 2 | IRDAI | ⚠️ Derived business logic only, not tied to specific extracted clause |
| GRACE_PERIOD | 1 | IRDAI | ℹ️ Not independently evaluated |
| DOCUMENTATION_MISSING | 1 | HDFC 2021 | ✅ Evaluator implemented + tested |
| **ELIGIBILITY_FAILURE** | **0** | — | ❌ No rules extracted; evaluator honestly empty |

## C. Source documents

| Document | Insurer | Product | Version | Pages | Source | Provenance | Verification Status |
|---|---|---|---|---|---|---|---|
| STAR_ASSURE_2026_CIS | Star Health | Star Health Assure | V.7/2026 | 20 | starhealth.in CDN (official) | REAL, extracted text | ✅ hash present (EXTRACTED_TEXT) |
| HDFC_OPTIMA_SECURE_2026_POLICY_WORDING | HDFC ERGO | my:Optima Secure | 2026-04-02+ | 60 (42 extracted) | hdfcergo.com (official) | REAL, extracted text | ⚠️ UIN conflict; partial extraction |
| HDFC_OPTIMA_SECURE_2026_CIS | HDFC ERGO | my:Optima Secure | current | 12 | hdfcergo.com (official) | REAL, extracted text | ⚠️ UIN conflict |
| HDFC_OPTIMA_SECURE_2021_HISTORICAL | HDFC ERGO | my:Optima Secure | Aug 2021 | 24 | hdfcergo.com (official, archived) | REAL, extracted text | ✅ Verified, isolated |
| IRDAI_MASTER_CIRCULAR_2024 | IRDAI (regulator) | N/A | 29-May-2024 | 17 | taxguru.in (third-party verbatim republication) | REAL text, unofficial hosting | ⚠️ Not fetched from irdai.gov.in directly (robots-blocked) |

## D. Dataset provenance legend

| Dataset/Component | REAL / SYNTHETIC / DERIVED | Meaning |
|---|---|---|
| `source_documents.csv` | REAL | Extracted text of actually-published insurer/regulator documents |
| `policy_inventory.csv` | REAL | Policy version metadata derived directly from the above |
| `policy_rule_candidates.csv` | REAL (DERIVED extraction) | Individual clauses transcribed from real document text, with page citations. The *transcription* is a derived artifact; the *content* is real. |
| `data/synthetic/claims.json` | SYNTHETIC | Fabricated test claims — no real patients, no real insurer decisions |
| `claims.json` → `expected_result_provenance` | DERIVED_FROM_REAL_RULE | Expected PASS/FAIL/WARNING computed from a real rule's real threshold, applied to a synthetic claim |
| `backend/app/rules/policy_status.py` derived checks | DERIVED_LOGIC_NOT_FROM_SOURCE_RULE | Reasonable business logic, explicitly NOT backed by a specific extracted document clause |
| `backend/claim_validator.db` | Mixed | Seeded from the REAL CSVs above; any claims created via the API for testing are SYNTHETIC |

**What this dataset is NOT:** it contains no real patient data, no real
claim outcomes, no real insurer approval/rejection decisions, and no
invented policy rules. Every numeric threshold in
`policy_rule_candidates.csv` traces to a quoted `source_text` from a real
document.
