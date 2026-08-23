# RAG Evaluation (Real Numbers Only)

All figures below come from actually running `scripts/test_rag.py` and
`backend/tests/test_rag.py` on this session's build — none are
estimated or asserted without a corresponding run.

## Index statistics

- Documents indexed: **5** (all real source documents in the dataset)
- Total chunks: **129**
  - `star_assure_2026_v1`: 72 chunks
  - `hdfc_optima_secure_2026_v1`: 23 chunks
  - `hdfc_optima_secure_2021_v1`: 10 chunks
  - Regulatory (IRDAI, unscoped to any policy version): 24 chunks
- Embedding method: **TF-IDF (scikit-learn), local, no API key or network call**
- LLM provider for answer generation: **Extractive (no LLM call)** — no
  `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` configured in this environment
- Retrieval similarity threshold: **0.08** (cosine similarity), calibrated
  empirically — see `docs/rag.md` for why this exact value was chosen

## Demo questions (`scripts/test_rag.py`)

Questions tested: **7**
Correctly found/refused (found=True when evidence exists, found=False
when it genuinely doesn't): **7/7**
Correct source document present in citations (when found=True): **7/7**

| # | Question | Policy Version | Expected | Actual | Result |
|---|---|---|---|---|---|
| 1 | "Does this policy cover cataract treatment?" | star_assure_2026_v1 | found, STAR_ASSURE_2026_CIS | found=True, citations include page 8 (score 0.143) | ✅ (see note below) |
| 2 | "What is the waiting period for specified diseases?" | star_assure_2026_v1 | found, page 8 | found=True, top citation page 8 (score 0.432) | ✅ |
| 3 | "What is the policy's initial waiting period?" | star_assure_2026_v1 | found, page 7 | found=True, citations include page 7 (score 0.178) but top-ranked was page 3 (score 0.191) | ⚠️ found correct document, but NOT top-ranked (see limitation below) |
| 4 | "Is preauthorization required?" | star_assure_2026_v1 | found | found=True, 1 citation (page 15, score 0.125) | ✅ |
| 5 | "What is the room rent limit?" | star_assure_2026_v1 | found, page 10 | found=True, top citation page 10 (score 0.419) | ✅ |
| 6 | "What is the initial waiting period?" | hdfc_optima_secure_2021_v1 | found, page 2 | found=True, 1 citation page 2 (score 0.095) | ✅ (borderline score, just above threshold) |
| 7 | "What is the recipe for chocolate chip cookies?" | star_assure_2026_v1 | NOT found | found=False, "Not found in the selected policy source." | ✅ |

**Retrieval success rate: 7/7 (100%) correctly found evidence or correctly refused.**
**Citation document correctness: 7/7 (100%).**
**Top-ranked passage correctness (the single best-scored chunk being the
single most relevant one, not just "the right document somewhere in the
list"): 5/7 (71%)** — see limitation below. This distinction matters and
is reported separately rather than folded into the headline number.

## Policy-version isolation

- `test_hdfc_question_never_returns_star_chunks`: **PASS**
- `test_star_question_never_returns_hdfc_chunks`: **PASS**
- `test_same_question_scoped_correctly_across_both_insurers` (the same
  question, "What is the initial waiting period?", asked against both
  insurers, verifying zero document-set overlap): **PASS**

**Cross-version leakage rate: 0/2 tested query pairs showed any leakage.**

## Unsupported-question refusal

- Genuinely zero-vocabulary-overlap question ("chocolate chip cookies"):
  refused correctly, similarity score **0.0**.
- A second zero-overlap question ("cricket world cup 2011"): refused
  correctly, similarity score **0.0**.

**Unsupported questions correctly refused: 2/2 tested (100%).**

## Citation correctness

- `test_citations_correspond_to_real_stored_chunks`: every citation's
  `chunk_id` was verified to exist in the actual persisted chunk index —
  **PASS**
- `test_citations_have_correct_policy_version`: every citation's
  underlying chunk was verified to belong to the requested
  `policy_version_id` — **PASS**

## No-decision guarantee

`test_rag_cannot_change_validation_severity`: ran the deterministic rule
engine on a claim, then asked two RAG questions about that same claim,
then re-ran the rule engine — **the set of (rule_id, severity) pairs was
byte-identical before and after**. **PASS.**

## Test suite totals

- Existing backend tests (dataset/API/rule-engine, unchanged): **24/24 PASS**
- New RAG tests (`backend/tests/test_rag.py`): **10/10 PASS**
- **Total: 34/34 PASS**

## Known, disclosed limitation: TF-IDF surface-lexical-overlap false ranking

During testing, a short section-header chunk reading *"6. Exclusions
(What the policy does not cover) - Standard Exclusions:"* was found to
score moderately-to-highly (0.15–0.60 across different test queries)
against almost any question phrased like "does this policy cover X?",
purely because it shares generic function words ("policy", "does",
"cover") with typical coverage questions — regardless of whether the
actual answer is in that chunk.

**This is why "top-ranked passage correctness" (5/7) is reported
separately and lower than "correct document was found somewhere in
citations" (7/7).** For questions 1 and 3 above, the substantively
correct passage was retrieved and returned to the caller (in `citations`
and `sources`, and in the concatenated `answer` text — see `answer.py`'s
`ExtractiveProvider`, which returns ALL retrieved passages, not just the
top-ranked one) — but it was not the single highest-scored chunk.

This is a genuine, structural weakness of bag-of-words TF-IDF on a small,
domain-narrow corpus, not a bug that was silently accepted: it is
disclosed here and in `docs/rag.md`, and the mitigation (returning all
retrieved passages rather than only the top one) is a deliberate design
choice made specifically because of this finding.

**No fabricated "LLM accuracy" percentage is reported anywhere in this
document** — every number above corresponds to an actual test run against
the actual TF-IDF index built from the actual extracted source text.
