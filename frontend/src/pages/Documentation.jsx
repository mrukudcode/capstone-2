export default function Documentation() {
  return (
    <div>
      <h1>Documentation</h1>
      <div className="evidence-panel">
        <h2 style={{ marginTop: 0 }}>What this system is</h2>
        <p>
          An <strong>Explainable Pre-Submission Health Insurance Claim Rule
          Validator</strong>. It checks a claim's fields against policy rules
          extracted from real, source-cited insurer and IRDAI documents, and
          reports PASS / WARNING / PARTIAL_DEDUCTION / FAIL per rule, with an
          overall recommendation of SUBMISSION_READY, HUMAN_REVIEW_NEEDED, or
          FIX_BEFORE_SUBMISSION.
        </p>
        <h2>What this system is NOT</h2>
        <p>
          It does <strong>not</strong> predict or guarantee an insurer's final
          adjudication decision. It never claims "the insurance company will
          definitely accept this claim." Financial figures are labelled
          "Rule-based estimate — not a guaranteed insurer payout."
        </p>
        <h2>Data provenance</h2>
        <ul>
          <li><strong>Real</strong>: source documents, extracted text, structured policy rules — all trace to a document and page.</li>
          <li><strong>Synthetic</strong>: test claims created through this UI or generated in data/synthetic/claims.json.</li>
          <li><strong>Derived</strong>: expected test results computed from real rule thresholds.</li>
        </ul>
        <h2>Known limitations</h2>
        <ul>
          <li>Some HDFC ERGO 2026 rules are flagged NEEDS_REVIEW due to an unresolved UIN conflict between two official documents — these are excluded from automatic evaluation.</li>
          <li>Extracted text, not original PDF bytes, backs every source document (environment limitation).</li>
          <li>RAG and FHIR export are not yet implemented.</li>
        </ul>
      </div>
    </div>
  );
}
