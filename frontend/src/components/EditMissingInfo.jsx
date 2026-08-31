import { useState } from 'react';
import { api, ApiError } from '../services/api';

const BOOL_FIELDS = [
  ['injury_related', 'Hospitalization due to injury'],
  ['self_inflicted_injury', 'Self-inflicted injury'],
  ['substance_abuse_related', 'Substance-abuse related'],
  ['substance_abuse_test_done', 'Substance-abuse test conducted'],
  ['medico_legal_case', 'Medico-legal case'],
  ['police_reported', 'Reported to police'],
];

export default function EditMissingInfo({ claim, onUpdated }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    continuous_coverage_since: '',
    previous_insurer_name: '',
    hospital_type: '',
    admission_type: '',
    discharge_status: '',
    comorbidities: '',
    additional_diagnoses: '',
    procedure_2_description: '',
    procedure_2_code: '',
    procedure_3_description: '',
    procedure_3_code: '',
    preauth_number: '',
    fir_number: '',
    delivery_date: '',
    gravida_status: '',
    policy_document_received_date: '',
    additional_clinical_details: '',
    injury_related: '',
    self_inflicted_injury: '',
    substance_abuse_related: '',
    substance_abuse_test_done: '',
    medico_legal_case: '',
    police_reported: '',
  });

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSave(e) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const payload = { ...form };
      Object.keys(payload).forEach((k) => {
        if (payload[k] === '') delete payload[k];
        else if (['injury_related', 'self_inflicted_injury', 'substance_abuse_related',
                   'substance_abuse_test_done', 'medico_legal_case', 'police_reported'].includes(k)) {
          payload[k] = payload[k] === 'true';
        }
      });
      if (Object.keys(payload).length === 0) {
        setError('Fill in at least one field before saving.');
        setSaving(false);
        return;
      }
      await api.updateClaim(claim.claim_id, payload);
      await onUpdated();
      setOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="secondary" onClick={() => setOpen(true)} style={{ marginTop: 12 }}>
        Add Missing Information
      </button>
    );
  }

  return (
    <div style={{ marginTop: 16 }}>
      <h2>Add Missing Information</h2>
      <p className="page-subtitle">
        Fill in only the fields relevant to the WARNING results above, then save and re-run validation.
        Fields left blank are not changed.
      </p>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <form className="claim-form" onSubmit={handleSave}>
        <div>
          <label>Continuous Coverage Since</label>
          <input type="date" value={form.continuous_coverage_since}
            onChange={(e) => update('continuous_coverage_since', e.target.value)} />
        </div>
        <div>
          <label>Previous Insurer</label>
          <input value={form.previous_insurer_name}
            onChange={(e) => update('previous_insurer_name', e.target.value)} />
        </div>

        <div>
          <label>Hospital Type</label>
          <select value={form.hospital_type} onChange={(e) => update('hospital_type', e.target.value)}>
            <option value="">Select…</option>
            <option value="NETWORK">Network</option>
            <option value="NON_NETWORK">Non-Network</option>
          </select>
        </div>
        <div>
          <label>Admission Type</label>
          <select value={form.admission_type} onChange={(e) => update('admission_type', e.target.value)}>
            <option value="">Select…</option>
            <option value="EMERGENCY">Emergency</option>
            <option value="PLANNED">Planned</option>
            <option value="DAY_CARE">Day Care</option>
            <option value="MATERNITY">Maternity</option>
          </select>
        </div>

        <div>
          <label>Discharge Status</label>
          <select value={form.discharge_status} onChange={(e) => update('discharge_status', e.target.value)}>
            <option value="">Select…</option>
            <option value="HOME">Home</option>
            <option value="TRANSFERRED">Transferred</option>
            <option value="DECEASED">Deceased</option>
          </select>
        </div>
        <div>
          <label>Preauthorization Number</label>
          <input value={form.preauth_number} onChange={(e) => update('preauth_number', e.target.value)} />
        </div>

        <div className="field-full">
          <label>Co-morbidities (comma-separated)</label>
          <input value={form.comorbidities} onChange={(e) => update('comorbidities', e.target.value)} />
        </div>
        <div className="field-full">
          <label>Additional Diagnoses (comma-separated)</label>
          <input value={form.additional_diagnoses} onChange={(e) => update('additional_diagnoses', e.target.value)} />
        </div>

        <div>
          <label>Procedure 2</label>
          <input value={form.procedure_2_description} onChange={(e) => update('procedure_2_description', e.target.value)} />
        </div>
        <div>
          <label>Procedure 2 Code</label>
          <input value={form.procedure_2_code} onChange={(e) => update('procedure_2_code', e.target.value)} />
        </div>
        <div>
          <label>Procedure 3</label>
          <input value={form.procedure_3_description} onChange={(e) => update('procedure_3_description', e.target.value)} />
        </div>
        <div>
          <label>Procedure 3 Code</label>
          <input value={form.procedure_3_code} onChange={(e) => update('procedure_3_code', e.target.value)} />
        </div>

        {BOOL_FIELDS.map(([field, label]) => (
          <div key={field}>
            <label>{label}</label>
            <select value={form[field]} onChange={(e) => update(field, e.target.value)}>
              <option value="">Unknown</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
        ))}

        <div>
          <label>FIR Number (if applicable)</label>
          <input value={form.fir_number} onChange={(e) => update('fir_number', e.target.value)} />
        </div>
        <div>
          <label>Delivery Date (maternity only)</label>
          <input type="date" value={form.delivery_date} onChange={(e) => update('delivery_date', e.target.value)} />
        </div>
        <div>
          <label>Gravida Status (maternity only)</label>
          <input value={form.gravida_status} onChange={(e) => update('gravida_status', e.target.value)} />
        </div>
        <div>
          <label>Policy Document Received Date</label>
          <input type="date" value={form.policy_document_received_date}
            onChange={(e) => update('policy_document_received_date', e.target.value)} />
        </div>

        <div className="field-full">
          <label>Additional Clinical / Claim Details</label>
          <textarea rows={3} value={form.additional_clinical_details}
            onChange={(e) => update('additional_clinical_details', e.target.value)}
            placeholder="e.g. refractive error measured at 6.5 dioptres" />
        </div>

        <div className="field-full">
          <button className="primary" type="submit" disabled={saving}>
            {saving ? 'Saving…' : 'Save & Re-run Validation'}
          </button>
          <button type="button" className="secondary" style={{ marginLeft: 8 }}
            onClick={() => setOpen(false)} disabled={saving}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}