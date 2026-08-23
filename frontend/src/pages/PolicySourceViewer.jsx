import { useEffect, useState } from 'react';
import { api, ApiError } from '../services/api';
import { Loading, ErrorBox } from '../components/Common';

export default function PolicySourceViewer() {
  const [policies, setPolicies] = useState(null);
  const [selectedPolicyId, setSelectedPolicyId] = useState('');
  const [sources, setSources] = useState(null);
  const [selectedDocId, setSelectedDocId] = useState('');
  const [docText, setDocText] = useState(null);
  const [error, setError] = useState(null);
  const [loadingText, setLoadingText] = useState(false);

  useEffect(() => {
    api.listPolicies().then(setPolicies).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  function handleSelectPolicy(policyId) {
    setSelectedPolicyId(policyId);
    setSources(null);
    setDocText(null);
    setSelectedDocId('');
    if (!policyId) return;
    api.getPolicySources(policyId).then(setSources).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }

  function handleSelectDoc(docId) {
    setSelectedDocId(docId);
    setDocText(null);
    if (!docId) return;
    setLoadingText(true);
    api.getDocumentText(docId)
      .then(setDocText)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setLoadingText(false));
  }

  if (error) return <ErrorBox message={error} />;
  if (!policies) return <Loading label="Loading policies…" />;

  return (
    <div>
      <h1>Policy Source Viewer</h1>
      <p className="page-subtitle">
        Browse the actual extracted source text behind this dataset's rules —
        this demonstrates provenance directly, not a paraphrase.
      </p>

      <div className="claim-form" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div>
          <label>Policy Version</label>
          <select value={selectedPolicyId} onChange={(e) => handleSelectPolicy(e.target.value)}>
            <option value="">Select a policy…</option>
            {policies.map(p => (
              <option key={p.policy_id} value={p.policy_id}>{p.insurer} — {p.product}</option>
            ))}
          </select>
        </div>
        <div>
          <label>Source Document</label>
          <select value={selectedDocId} onChange={(e) => handleSelectDoc(e.target.value)} disabled={!sources}>
            <option value="">{sources ? 'Select a document…' : 'Select a policy first'}</option>
            {sources && sources.map(d => (
              <option key={d.document_id} value={d.document_id}>
                {d.document_id} ({d.page_count} pages, {d.hash_type})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loadingText && <Loading label="Loading extracted text…" />}
      {docText && (
        <div className="evidence-panel">
          <div className="financial-row"><span>Document</span><span>{docText.document_id}</span></div>
          <div className="financial-row"><span>Source URL</span><span style={{ wordBreak: 'break-all' }}>{docText.source_url}</span></div>
          <div className="financial-row"><span>Hash Type</span><span>{docText.hash_type}</span></div>
          <div className="financial-row"><span>Page Count</span><span>{docText.page_count}</span></div>
          <h2 style={{ marginTop: 16 }}>Extracted Text</h2>
          <div className="evidence-passage">{docText.text}</div>
        </div>
      )}
    </div>
  );
}
