import { useState } from 'react';
import { api, ApiError } from '../services/api';
import { ErrorBox } from '../components/Common';

export default function PolicyUpload() {
  const [form, setForm] = useState({
    insurer: '',
    product: '',
    uin: '',
    policy_version_id: '',
    document_type: 'POLICY_WORDING',
  });

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!file) {
      setError('Please choose a PDF file.');
      return;
    }

    if (
      !form.insurer ||
      !form.product ||
      !form.uin ||
      !form.policy_version_id
    ) {
      setError(
        'Insurer, Product, UIN, and Policy Version ID are all required.'
      );
      return;
    }

    const formData = new FormData();

    Object.entries(form).forEach(([k, v]) => {
      formData.append(k, v);
    });

    formData.append('file', file);

    setUploading(true);

    try {
      const r = await api.uploadPolicy(formData);
      setResult(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div>
      <h1>Upload Policy Document</h1>

      <p className="page-subtitle">
        Upload a policy CIS or Policy Wording PDF. Text is extracted with
        PyMuPDF, and rules are extracted with the Groq LLM. Every extracted
        rule is stored as <strong>review_status = PENDING</strong> and will
        not be auto-trusted until manually reviewed.
      </p>

      <ErrorBox message={error} />

      <form className="claim-form" onSubmit={handleSubmit}>
        <div>
          <label>Insurer Name *</label>
          <input
            value={form.insurer}
            onChange={(e) => update('insurer', e.target.value)}
            placeholder="e.g. ICICI Lombard General Insurance Company Limited"
          />
        </div>

        <div>
          <label>Product Name *</label>
          <input
            value={form.product}
            onChange={(e) => update('product', e.target.value)}
            placeholder="e.g. Complete Health Insurance"
          />
        </div>

        <div>
          <label>UIN *</label>
          <input
            value={form.uin}
            onChange={(e) => update('uin', e.target.value)}
            placeholder="e.g. ICIHLIP26058V012526"
          />
        </div>

        <div>
          <label>Policy Version ID *</label>
          <input
            value={form.policy_version_id}
            onChange={(e) =>
              update('policy_version_id', e.target.value)
            }
            placeholder="e.g. icici_complete_health_2026_v1"
          />
        </div>

        <div>
          <label>Document Type</label>

          <select
            value={form.document_type}
            onChange={(e) =>
              update('document_type', e.target.value)
            }
          >
            <option value="POLICY_WORDING">
              Policy Wording
            </option>

            <option value="CIS">
              Customer Information Sheet (CIS)
            </option>
          </select>
        </div>

        <div>
          <label>PDF File *</label>

          <input
            type="file"
            accept="application/pdf"
            onChange={(e) =>
              setFile(e.target.files?.[0] || null)
            }
          />
        </div>

        <div className="field-full">
          <button
            className="primary"
            type="submit"
            disabled={uploading}
          >
            {uploading
              ? 'Extracting text and rules…'
              : 'Upload & Extract'}
          </button>
        </div>
      </form>

      {result && (
        <div style={{ marginTop: 24 }}>
          <h2>Extraction Complete</h2>

          <p className="page-subtitle">
            {result.message}
          </p>

          <p>
            Document ID:{' '}
            <strong>{result.document_id}</strong>
            {' | '}
            Policy Version:{' '}
            <strong>{result.policy_version_id}</strong>
            {' | '}
            Pages:{' '}
            <strong>{result.page_count}</strong>
            {' | '}
            Rules Extracted:{' '}
            <strong>{result.rules_extracted}</strong>
          </p>

          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Type</th>
                <th>Rule</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Page</th>
                <th>Confidence</th>
                <th>Source Text</th>
              </tr>
            </thead>

            <tbody>
              {result.rules.map((r) => (
                <tr key={r.candidate_id}>
                  <td>{r.candidate_id}</td>
                  <td>{r.rule_type}</td>
                  <td>{r.rule_name}</td>
                  <td>{r.value}</td>
                  <td>{r.unit}</td>
                  <td>{r.source_page}</td>
                  <td>{r.confidence}</td>
                  <td>{r.source_text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}