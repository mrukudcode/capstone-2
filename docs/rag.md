# RAG / Explainability Layer

## Purpose

Answers natural-language questions about a policy's documented wording,
scoped strictly to one `policy_version_id`, with citations back to the
real source document and page. **This layer never makes a PASS/FAIL/
WARNING decision** — that remains the sole responsibility of the
deterministic rule engine (`backend/app/rules/`). RAG only explains and
locates policy text.

## Architecture

```
Claim (has policy_version_db_id)
      ↓
policy_version_id resolved from the claim in the DATABASE
(client can never override this -- see api/qa.py)
      ↓
retrieve() -- filters chunks to ONLY this policy_version_id
              BEFORE computing any similarity score
      ↓
top-k chunks above a similarity threshold
      ↓
answer generation (extractive by default; optional LLM)
      ↓
{ answer, found, citations[], sources[] }
```

## Files

| File | Role |
|---|---|
| `backend/app/rag/chunking.py` | Splits real extracted-text documents into page-aware sub-chunks |
| `backend/app/rag/embeddings.py` | Builds/loads a local TF-IDF similarity index (scikit-learn) |
| `backend/app/rag/retrieve.py` | Policy-version-scoped retrieval; filters BEFORE scoring |
| `backend/app/rag/answer.py` | Answer generation; extractive by default, optional LLM provider |
| `backend/app/rag/service.py` | Orchestrates retrieve → threshold → answer → citations |
| `backend/app/api/qa.py` | `POST /claims/{claim_id}/questions`, `POST /policies/{policy_version_id}/questions` |
| `scripts/build_rag_index.py` | Builds the real index from `data/raw/` into `data/processed/chunks/` |
| `scripts/test_rag.py` | Runs the 7 required demo questions, prints real results |
| `backend/tests/test_rag.py` | 10 automated tests (retrieval, isolation, refusal, citations, no-decision) |

## Why TF-IDF, not sentence-transformers or a hosted embedding API

- No API key or network call is required — fully offline, reproducible.
- The corpus is small (129 chunks across 5 documents) — TF-IDF performs
  adequately at this scale without pulling in a multi-hundred-MB
  torch/transformers dependency.
- Satisfies the explicit project instruction: "a local embedding solution
  is preferred... do not add unnecessary infrastructure."

## Chunking strategy

Each source document's own `[PAGE N]`, `[PAGES X-Y]`, or (for the IRDAI
circular) `[Chapter..., p.N]` header markers are used as the page-citation
boundary — no new pagination scheme is invented. Within a page, text is
further split at paragraph/numbered-list-item boundaries so a single
distinguishing term (e.g. "cataract" among a 14-item disease list) isn't
diluted across an entire page's vocabulary. Fragments under 20 words are
merged with adjacent content rather than left as bare, over-weighted
section-header stubs (see "Known limitations" below for why this
threshold was chosen empirically, not arbitrarily).

**A citation's `page` field is either a real page number parsed from that
exact header, or the honest string `NOT_SPECIFIED_IN_SOURCE`** — never a
guessed number.

## Policy-version isolation — how it's actually enforced

`retrieve()` filters the candidate chunk indices to only those where
`chunk.policy_version_id == policy_version_id` **before** computing any
cosine similarity score (see `retrieve.py`). A chunk from another policy
version is never scored against the question at all, let alone ranked
or returned. This was verified directly: asking "What is the initial
waiting period?" (a question that both Star and HDFC could plausibly
answer) against each policy version returns completely disjoint
document sets — see `test_same_question_scoped_correctly_across_both_insurers`
in `backend/tests/test_rag.py`.

## Answer generation

Default provider: **`ExtractiveProvider`** — makes no LLM/API call at
all. Returns the retrieved passages verbatim, prefixed with a
deterministic "Based on [document] (page [N]):" lead-in. This is
architecturally incapable of hallucinating a policy fact, because it
never generates new text — only surfaces real retrieved text.

If `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is present in the environment,
an `OpenAIProvider`/`AnthropicProvider` is used instead to produce a more
natural-language summary of the *same* retrieved passages, under a system
prompt that explicitly forbids outside knowledge or inferring missing
terms. Neither was configured anywhere in this project prior to this
phase (confirmed by inspection) — extractive is genuinely the default in
this codebase, not a fallback that silently never triggers.

## Known limitations (disclosed, not hidden)

1. **TF-IDF ranks by lexical overlap, not true semantic meaning.** A short
   section-header chunk containing "(What the policy does not cover)"
   can score moderately high against almost any "does this policy cover
   X?" phrased question, purely on shared function words. This was
   observed directly during testing (see `docs/rag_evaluation.md`).
   Mitigation: the answer includes ALL retrieved passages (not just the
   top-ranked one), so the substantively correct passage is still visible
   even when it isn't ranked first.
2. **Insurance-domain-adjacent-but-unsupported questions are a known
   false-positive risk.** E.g. "does this cover skydiving/pet insurance"
   can still score above the similarity threshold because it shares
   generic insurance vocabulary with the corpus. **Genuinely off-domain
   questions (e.g. "recipe for chocolate chip cookies") are reliably
   refused with a score of exactly 0.0** — confirmed in testing.
3. **Regulatory (IRDAI) chunks are not scoped to any policy_version_id**
   by design (the circular applies to all insurers generally) — they are
   retrievable only via a separate `retrieve_regulatory()` function, kept
   deliberately unreachable from the policy-scoped `retrieve()` path so
   they can never leak into a claim-specific answer.
4. Star Health's full Policy Wording (only its CIS) and ~30% of HDFC's
   2026 Policy Wording were never ingested in earlier phases — the RAG
   corpus inherits this same coverage gap (see `docs/limitations.md`).
