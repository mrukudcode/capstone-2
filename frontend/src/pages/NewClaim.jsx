import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../services/api';
import { Loading, ErrorBox } from '../components/Common';

const REQUIRED = [
  'policy_version_id',
  'policy_start_date',
  'admission_date',
  'insured_age_at_entry',
  'sum_insured',
  'billed_amount',
];

export default function NewClaim() {
  const navigate = useNavigate();

  const [policies, setPolicies] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState('');

  // ==================================================
  // ICD-10 STATE
  // ==================================================

  const [diagnosisSearch, setDiagnosisSearch] = useState('');
  const [diagnosisResults, setDiagnosisResults] = useState([]);
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [showDiagnosisDropdown, setShowDiagnosisDropdown] = useState(false);
  const [selectedDiagnosis, setSelectedDiagnosis] = useState(null);

  // ==================================================
  // FORM
  // ==================================================

  const [form, setForm] = useState({
    claim_ref: '',

    // Policy
    policy_version_id: '',
    policy_start_date: '',
    policy_end_date: '',

    // Claim / insured
    insured_age_at_entry: '',
    sum_insured: '',

    // Hospitalisation
    admission_date: '',
    discharge_date: '',
    admission_type: '',
    claim_type: '',

    // Hospital
    hospital_type: '',

    // Room / billing
    room_type: '',
    room_rent_per_day: '',
    billed_amount: '',

    // Diagnosis
    diagnosis_code: '',
    diagnosis_description: '',

    // Primary procedure
    procedure_description: '',
    procedure_code: '',

    // Treatment / sub-limit
    treatment_category: '',
    category_billed_amount: '',

    // Preauthorization
    preauth_status: 'NONE',
    preauth_request_date: '',
    preauth_approval_date: '',

    // Claim notification
    notification_date: '',
    claim_filed_date: '',

    // Exclusions / special situations
    injury_related: '',
    self_inflicted_injury: '',
    substance_abuse_related: '',
    substance_abuse_test_done: '',

    // MLC
    medico_legal_case: '',
    police_reported: '',

    // Deductible
    deductible_opted: false,
    deductible_amount_opted: '',

    // Documents
    documents_submitted: '',
  });

  // ==================================================
  // LOAD POLICIES
  // ==================================================

  useEffect(() => {
    api.listPolicies()
      .then(setPolicies)
      .catch((e) => {
        setLoadError(
          e instanceof ApiError
            ? e.message
            : String(e)
        );
      });
  }, []);

  // ==================================================
  // ICD-10 SEARCH
  // ==================================================

  useEffect(() => {
    const query = diagnosisSearch.trim();

    if (query.length < 2) {
      setDiagnosisResults([]);
      setDiagnosisLoading(false);
      setShowDiagnosisDropdown(false);
      return;
    }

    if (
      selectedDiagnosis &&
      query === selectedDiagnosis.display
    ) {
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setDiagnosisLoading(true);

        const data = await api.searchICD10(query);

        const results = Array.isArray(data?.results)
          ? data.results
          : [];

        setDiagnosisResults(results);
        setShowDiagnosisDropdown(true);

      } catch (error) {
        console.error(
          'ICD-10 search failed:',
          error
        );

        setDiagnosisResults([]);
        setShowDiagnosisDropdown(true);

      } finally {
        setDiagnosisLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);

  }, [diagnosisSearch, selectedDiagnosis]);

  // ==================================================
  // SELECTED POLICY
  // ==================================================

  const selectedPolicy = policies?.find((p) =>
    p.versions.some(
      (v) =>
        v.policy_version_id ===
        form.policy_version_id
    )
  );

  const selectedVersion =
    selectedPolicy?.versions.find(
      (v) =>
        v.policy_version_id ===
        form.policy_version_id
    );

  // ==================================================
  // GENERIC UPDATE
  // ==================================================

  function update(field, value) {
    setForm((previous) => ({
      ...previous,
      [field]: value,
    }));
  }

  // ==================================================
  // REQUIRED FIELDS
  // ==================================================

  function missingFields() {
    return REQUIRED.filter(
      (field) => !form[field]
    );
  }

  // ==================================================
  // DIAGNOSIS INPUT
  // ==================================================

  function handleDiagnosisChange(value) {
    setDiagnosisSearch(value);

    setSelectedDiagnosis(null);

    setForm((previous) => ({
      ...previous,
      diagnosis_code: '',
      diagnosis_description: '',
    }));

    if (value.trim().length >= 2) {
      setShowDiagnosisDropdown(true);
    } else {
      setShowDiagnosisDropdown(false);
      setDiagnosisResults([]);
    }
  }

  // ==================================================
  // SELECT ICD-10
  // ==================================================

  function selectDiagnosis(item) {
    const diagnosis = {
      id: item.id,
      code: item.code,
      title: item.title,
      display: `${item.code} — ${item.title}`,
    };

    setSelectedDiagnosis(diagnosis);

    setForm((previous) => ({
      ...previous,
      diagnosis_code: item.code,
      diagnosis_description: item.title,
    }));

    setDiagnosisSearch(
      diagnosis.display
    );

    setShowDiagnosisDropdown(false);
    setDiagnosisResults([]);
  }

  // ==================================================
  // SUBMIT
  // ==================================================

  async function handleSubmit(e) {
    e.preventDefault();

    setSubmitError(null);

    const missing = missingFields();

    if (missing.length > 0) {
      setSubmitError(
        `Missing required field(s): ${missing.join(', ')}`
      );
      return;
    }

    // If user entered diagnosis text,
    // require selection from ICD-10.
    if (
      diagnosisSearch.trim() &&
      !selectedDiagnosis
    ) {
      setSubmitError(
        'Please select a diagnosis from the ICD-10 dropdown.'
      );
      return;
    }

    // Treatment category is required only when
    // the user wants the sub-limit evaluator to run.
    if (
      form.treatment_category &&
      !form.category_billed_amount
    ) {
      setSubmitError(
        'Please enter the Category Billed Amount when a treatment category is provided.'
      );
      return;
    }

    // Deductible amount is required when deductible is opted.
    if (
      form.deductible_opted &&
      !form.deductible_amount_opted
    ) {
      setSubmitError(
        'Please enter the deductible amount selected.'
      );
      return;
    }

    setSubmitting(true);
    setSubmitStatus('Creating claim...');

    try {
      const payload = {
        ...form,
      };

      // ==================================================
      // REMOVE EMPTY OPTIONAL FIELDS
      // ==================================================

      Object.keys(payload).forEach((key) => {
        if (payload[key] === '') {
          delete payload[key];
        }
      });

      // ==================================================
      // BOOLEAN CONVERSION
      // ==================================================

      const booleanFields = [
        'injury_related',
        'self_inflicted_injury',
        'substance_abuse_related',
        'substance_abuse_test_done',
        'medico_legal_case',
        'police_reported',
      ];

      booleanFields.forEach((field) => {
        if (payload[field] !== undefined) {
          payload[field] =
            payload[field] === true ||
            payload[field] === 'true';
        }
      });

      // ==================================================
      // NUMERIC CONVERSION
      // ==================================================

      const numericFields = [
        'insured_age_at_entry',
        'sum_insured',
        'room_rent_per_day',
        'billed_amount',
        'category_billed_amount',
        'deductible_amount_opted',
      ];

      numericFields.forEach((field) => {
        if (payload[field] !== undefined) {
          payload[field] =
            Number(payload[field]);
        }
      });

      // ==================================================
      // GENERATE CLAIM REFERENCE
      // ==================================================

      if (!payload.claim_ref) {
        payload.claim_ref =
          `CLAIM-${Date.now()}`;
      }

      console.log(
        'FINAL CLAIM PAYLOAD:',
        payload
      );

      // ==================================================
      // CREATE CLAIM
      // ==================================================

      const created =
        await api.createClaim(payload);

      // ==================================================
      // VALIDATE CLAIM
      // ==================================================

      setSubmitStatus(
        'Validating claim against policy rules...'
      );

      await api.validateClaim(
        created.claim_id
      );

      // ==================================================
      // NAVIGATE
      // ==================================================

      setSubmitStatus(
        'Validation complete. Loading results...'
      );

      navigate(
        `/claims/${created.claim_id}`
      );

    } catch (err) {
      console.error(
        'Claim submission error:',
        err
      );

      setSubmitError(
        err instanceof ApiError
          ? err.message
          : String(err)
      );

      setSubmitStatus('');

    } finally {
      setSubmitting(false);
    }
  }

  // ==================================================
  // LOADING
  // ==================================================

  if (loadError) {
    return (
      <ErrorBox
        message={
          `Failed to load policies: ${loadError}`
        }
      />
    );
  }

  if (!policies) {
    return (
      <Loading
        label="Loading policy list..."
      />
    );
  }

  // ==================================================
  // UI
  // ==================================================

  return (
    <div>

      <h1>New Claim</h1>

      <p className="page-subtitle">
        Enter the key details from the hospital claim
        and policy documents. The validator checks the
        claim against the selected policy rules before
        submission.
      </p>

      <ErrorBox message={submitError} />

      <form
        className="claim-form"
        onSubmit={handleSubmit}
      >

        {/* ========================================== */}
        {/* POLICY */}
        {/* ========================================== */}

        <div>

          <label>
            Insurer / Product *
          </label>

          <select
            required
            value={form.policy_version_id}
            onChange={(e) =>
              update(
                'policy_version_id',
                e.target.value
              )
            }
          >

            <option value="">
              Select a policy version...
            </option>

            {policies.map((p) => (

              <optgroup
                key={p.policy_id}
                label={`${p.insurer} — ${p.product}`}
              >

                {p.versions.map((v) => (

                  <option
                    key={v.policy_version_id}
                    value={v.policy_version_id}
                  >

                    {v.policy_version_id}
                    {' '}
                    (UIN {v.uin})

                    {v.uin_conflict_flag
                      ? ' — UIN CONFLICT'
                      : ''}

                  </option>

                ))}

              </optgroup>

            ))}

          </select>

        </div>

        {/* ========================================== */}
        {/* CLAIM REFERENCE */}
        {/* ========================================== */}

        <div>

          <label>
            Claim Reference
          </label>

          <input
            value={form.claim_ref}
            onChange={(e) =>
              update(
                'claim_ref',
                e.target.value
              )
            }
            placeholder="Auto-generated if left blank"
          />

        </div>

        {/* ========================================== */}
        {/* POLICY START DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Policy Start Date *
          </label>

          <input
            type="date"
            required
            value={form.policy_start_date}
            onChange={(e) =>
              update(
                'policy_start_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* POLICY END DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Policy End Date
          </label>

          <input
            type="date"
            value={form.policy_end_date}
            onChange={(e) =>
              update(
                'policy_end_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* AGE AT ENTRY */}
        {/* ========================================== */}

        <div>

          <label>
            Insured Age at Policy Entry *
          </label>

          <input
            type="number"
            min="0"
            max="120"
            required
            value={form.insured_age_at_entry}
            onChange={(e) =>
              update(
                'insured_age_at_entry',
                e.target.value
              )
            }
            placeholder="e.g. 45"
          />

          <small>
            Used for age-based co-payment rules.
          </small>

        </div>

        {/* ========================================== */}
        {/* SUM INSURED */}
        {/* ========================================== */}

        <div>

          <label>
            Sum Insured (Rs.) *
          </label>

          <input
            type="number"
            min="0"
            required
            value={form.sum_insured}
            onChange={(e) =>
              update(
                'sum_insured',
                e.target.value
              )
            }
            placeholder="e.g. 500000"
          />

          <small>
            Used for room-rent and sub-limit calculations.
          </small>

        </div>

        {/* ========================================== */}
        {/* ADMISSION DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Admission Date *
          </label>

          <input
            type="date"
            required
            value={form.admission_date}
            onChange={(e) =>
              update(
                'admission_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* DISCHARGE DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Discharge Date
          </label>

          <input
            type="date"
            value={form.discharge_date}
            onChange={(e) =>
              update(
                'discharge_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* ADMISSION TYPE */}
        {/* ========================================== */}

        <div>

          <label>
            Admission Type
          </label>

          <select
            value={form.admission_type}
            onChange={(e) =>
              update(
                'admission_type',
                e.target.value
              )
            }
          >

            <option value="">
              Select...
            </option>

            <option value="EMERGENCY">
              Emergency
            </option>

            <option value="PLANNED">
              Planned
            </option>

            <option value="DAY_CARE">
              Day Care
            </option>

            <option value="MATERNITY">
              Maternity
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* CLAIM TYPE */}
        {/* ========================================== */}

        <div>

          <label>
            Claim Type
          </label>

          <select
            value={form.claim_type}
            onChange={(e) =>
              update(
                'claim_type',
                e.target.value
              )
            }
          >

            <option value="">
              Select...
            </option>

            <option value="EMERGENCY">
              Emergency
            </option>

            <option value="PLANNED">
              Planned
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* HOSPITAL TYPE */}
        {/* ========================================== */}

        <div>

          <label>
            Hospital Type
          </label>

          <select
            value={form.hospital_type}
            onChange={(e) =>
              update(
                'hospital_type',
                e.target.value
              )
            }
          >

            <option value="">
              Select...
            </option>

            <option value="NETWORK">
              Network Hospital
            </option>

            <option value="NON_NETWORK">
              Non-Network Hospital
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* ROOM TYPE */}
        {/* ========================================== */}

        <div>

          <label>
            Room Type
          </label>

          <select
            value={form.room_type}
            onChange={(e) =>
              update(
                'room_type',
                e.target.value
              )
            }
          >

            <option value="">
              Select...
            </option>

            <option value="SHARED">
              Shared
            </option>

            <option value="SINGLE_PRIVATE">
              Single Private
            </option>

            <option value="ANY">
              Any Room
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* ROOM RENT */}
        {/* ========================================== */}

        <div>

          <label>
            Room Rent Per Day (Rs.)
          </label>

          <input
            type="number"
            min="0"
            value={form.room_rent_per_day}
            onChange={(e) =>
              update(
                'room_rent_per_day',
                e.target.value
              )
            }
            placeholder="e.g. 5000"
          />

          <small>
            Required when the policy contains a room-rent limit.
          </small>

        </div>

        {/* ========================================== */}
        {/* BILLED AMOUNT */}
        {/* ========================================== */}

        <div>

          <label>
            Total Billed Amount (Rs.) *
          </label>

          <input
            type="number"
            min="0"
            required
            value={form.billed_amount}
            onChange={(e) =>
              update(
                'billed_amount',
                e.target.value
              )
            }
            placeholder="e.g. 125000"
          />

          <small>
            Used for co-pay, deductible and financial calculations.
          </small>

        </div>

        {/* ========================================== */}
        {/* ICD-10 DIAGNOSIS */}
        {/* ========================================== */}

        <div
          className="field-full"
          style={{
            position: 'relative',
          }}
        >

          <label>
            Diagnosis
          </label>

          <input
            value={diagnosisSearch}
            onChange={(e) =>
              handleDiagnosisChange(
                e.target.value
              )
            }
            onFocus={() => {

              if (
                diagnosisResults.length > 0
              ) {
                setShowDiagnosisDropdown(true);
              }

            }}
            placeholder="Search ICD-10 diagnosis..."
            autoComplete="off"
          />

          {diagnosisLoading && (

            <div
              style={{
                marginTop: '6px',
                fontSize: '14px',
                color: '#666',
              }}
            >
              Searching ICD-10...
            </div>

          )}

          {showDiagnosisDropdown &&
            diagnosisResults.length > 0 && (

            <div
              style={{
                position: 'absolute',
                left: 0,
                right: 0,
                top: '100%',
                zIndex: 9999,
                background: '#ffffff',
                border: '1px solid #ccc',
                borderRadius: '6px',
                maxHeight: '300px',
                overflowY: 'auto',
                boxShadow:
                  '0 4px 12px rgba(0,0,0,0.15)',
              }}
            >

              {diagnosisResults.map(
                (item) => (

                  <div
                    key={
                      item.id ||
                      item.code
                    }

                    onMouseDown={(e) => {
                      e.preventDefault();

                      selectDiagnosis(
                        item
                      );
                    }}

                    style={{
                      padding: '12px',
                      cursor: 'pointer',
                      borderBottom:
                        '1px solid #eee',
                    }}
                  >

                    <div>
                      <strong>
                        {item.code}
                      </strong>
                    </div>

                    <div
                      style={{
                        marginTop: '4px',
                        fontSize: '14px',
                      }}
                    >
                      {item.title}
                    </div>

                  </div>

                )
              )}

            </div>

          )}

          {showDiagnosisDropdown &&
            !diagnosisLoading &&
            diagnosisSearch.trim().length >= 2 &&
            diagnosisResults.length === 0 && (

            <div
              style={{
                marginTop: '6px',
                fontSize: '14px',
                color: '#777',
              }}
            >
              No ICD-10 diagnosis found.
            </div>

          )}

        </div>

        {/* ========================================== */}
        {/* ICD CODE */}
        {/* ========================================== */}

        <div>

          <label>
            ICD-10 Code
          </label>

          <input
            value={form.diagnosis_code}
            readOnly
            placeholder="Select diagnosis above"
          />

        </div>

        {/* ========================================== */}
        {/* DIAGNOSIS DESCRIPTION */}
        {/* ========================================== */}

        <div className="field-full">

          <label>
            Selected Diagnosis
          </label>

          <input
            value={
              form.diagnosis_description
            }
            readOnly
            placeholder="Selected diagnosis will appear here"
          />

        </div>

        {/* ========================================== */}
        {/* PRIMARY PROCEDURE */}
        {/* ========================================== */}

        <div className="field-full">

          <label>
            Primary Procedure
          </label>

          <input
            value={form.procedure_description}
            onChange={(e) =>
              update(
                'procedure_description',
                e.target.value
              )
            }
            placeholder="e.g. Cataract surgery, Appendectomy, Knee replacement"
          />

          <small>
            Enter the main procedure performed during hospitalization.
            This is used to evaluate procedure-related exclusions.
          </small>

        </div>

        {/* ========================================== */}
        {/* PROCEDURE CODE */}
        {/* ========================================== */}

        <div>

          <label>
            Procedure Code
          </label>

          <input
            value={form.procedure_code}
            onChange={(e) =>
              update(
                'procedure_code',
                e.target.value
              )
            }
            placeholder="e.g. 00142"
          />

          <small>
            Enter the applicable procedure code if available.
          </small>

        </div>

        {/* ========================================== */}
        {/* TREATMENT CATEGORY */}
        {/* ========================================== */}

        <div>

          <label>
            Treatment Category
          </label>

          <select
            value={form.treatment_category}
            onChange={(e) =>
              update(
                'treatment_category',
                e.target.value
              )
            }
          >

            <option value="">
              Not applicable / Select...
            </option>

            <option value="HOME CARE TREATMENT">
              Home Care Treatment
            </option>

            <option value="AIR AMBULANCE">
              Air Ambulance
            </option>

          </select>

          <small>
            Select only if the claim contains a relevant sub-limit category.
          </small>

        </div>

        {/* ========================================== */}
        {/* CATEGORY BILLED AMOUNT */}
        {/* ========================================== */}

        <div>

          <label>
            Category Billed Amount (Rs.)
          </label>

          <input
            type="number"
            min="0"
            value={form.category_billed_amount}
            onChange={(e) =>
              update(
                'category_billed_amount',
                e.target.value
              )
            }
            placeholder="e.g. 50000"
          />

          <small>
            Used for treatment-category sub-limit checks.
          </small>

        </div>

        {/* ========================================== */}
        {/* PREAUTH STATUS */}
        {/* ========================================== */}

        <div>

          <label>
            Preauthorization Status
          </label>

          <select
            value={form.preauth_status}
            onChange={(e) =>
              update(
                'preauth_status',
                e.target.value
              )
            }
          >

            <option value="NONE">
              None
            </option>

            <option value="REQUESTED">
              Requested
            </option>

            <option value="APPROVED">
              Approved
            </option>

            <option value="DENIED">
              Denied
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* PREAUTH REQUEST DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Preauthorization Request Date
          </label>

          <input
            type="date"
            value={
              form.preauth_request_date
            }
            onChange={(e) =>
              update(
                'preauth_request_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* PREAUTH APPROVAL DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Preauthorization Approval Date
          </label>

          <input
            type="date"
            value={
              form.preauth_approval_date
            }
            onChange={(e) =>
              update(
                'preauth_approval_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* NOTIFICATION DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Claim Notification Date
          </label>

          <input
            type="date"
            value={form.notification_date}
            onChange={(e) =>
              update(
                'notification_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* CLAIM FILED DATE */}
        {/* ========================================== */}

        <div>

          <label>
            Claim Filed Date
          </label>

          <input
            type="date"
            value={form.claim_filed_date}
            onChange={(e) =>
              update(
                'claim_filed_date',
                e.target.value
              )
            }
          />

        </div>

        {/* ========================================== */}
        {/* INJURY */}
        {/* ========================================== */}

        <div>

          <label>
            Injury Related?
          </label>

          <select
            value={form.injury_related}
            onChange={(e) =>
              update(
                'injury_related',
                e.target.value
              )
            }
          >

            <option value="">
              Not specified
            </option>

            <option value="true">
              Yes
            </option>

            <option value="false">
              No
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* SELF INFLICTED */}
        {/* ========================================== */}

        <div>

          <label>
            Self-Inflicted Injury?
          </label>

          <select
            value={
              form.self_inflicted_injury
            }
            onChange={(e) =>
              update(
                'self_inflicted_injury',
                e.target.value
              )
            }
          >

            <option value="">
              Not specified
            </option>

            <option value="true">
              Yes
            </option>

            <option value="false">
              No
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* SUBSTANCE ABUSE */}
        {/* ========================================== */}

        <div>

          <label>
            Substance Abuse Related?
          </label>

          <select
            value={
              form.substance_abuse_related
            }
            onChange={(e) =>
              update(
                'substance_abuse_related',
                e.target.value
              )
            }
          >

            <option value="">
              Not specified
            </option>

            <option value="true">
              Yes
            </option>

            <option value="false">
              No
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* MLC */}
        {/* ========================================== */}

        <div>

          <label>
            Medico-Legal Case?
          </label>

          <select
            value={
              form.medico_legal_case
            }
            onChange={(e) =>
              update(
                'medico_legal_case',
                e.target.value
              )
            }
          >

            <option value="">
              Not specified
            </option>

            <option value="true">
              Yes
            </option>

            <option value="false">
              No
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* DEDUCTIBLE */}
        {/* ========================================== */}

        <div>

          <label>
            Optional Deductible Selected?
          </label>

          <select
            value={
              form.deductible_opted
                ? 'true'
                : 'false'
            }
            onChange={(e) =>
              update(
                'deductible_opted',
                e.target.value === 'true'
              )
            }
          >

            <option value="false">
              No
            </option>

            <option value="true">
              Yes
            </option>

          </select>

        </div>

        {/* ========================================== */}
        {/* DEDUCTIBLE AMOUNT */}
        {/* ========================================== */}

        {form.deductible_opted && (

          <div>

            <label>
              Deductible Amount (Rs.)
            </label>

            <select
              value={
                form.deductible_amount_opted
              }
              onChange={(e) =>
                update(
                  'deductible_amount_opted',
                  e.target.value
                )
              }
            >

              <option value="">
                Select...
              </option>

              <option value="50000">
                Rs. 50,000
              </option>

              <option value="100000">
                Rs. 1,00,000
              </option>

            </select>

          </div>

        )}

        {/* ========================================== */}
        {/* DOCUMENTS */}
        {/* ========================================== */}

        <div className="field-full">

          <label>
            Documents Submitted
          </label>

          <textarea
            rows={2}
            value={
              form.documents_submitted
            }
            onChange={(e) =>
              update(
                'documents_submitted',
                e.target.value
              )
            }
            placeholder="e.g. claim_form, discharge_summary, bills, KYC"
          />

        </div>

        {/* ========================================== */}
        {/* UIN WARNING */}
        {/* ========================================== */}

        {selectedVersion?.uin_conflict_flag && (

          <div className="field-full">

            <ErrorBox
              message={
                'Warning: the selected policy version has an unresolved UIN conflict. Rules for it will not auto-evaluate and the claim will be marked Human Review Needed.'
              }
            />

          </div>

        )}

        {/* ========================================== */}
        {/* SUBMIT */}
        {/* ========================================== */}

        <div className="field-full">

          <button
            className="primary"
            type="submit"
            disabled={submitting}
          >

            {submitting
              ? 'Submitting...'
              : 'Create & Validate Claim'}

          </button>

          {submitting && submitStatus && (

            <p
              style={{
                marginTop: '10px',
                fontSize: '14px',
                color: '#666',
              }}
            >
              {submitStatus}
            </p>

          )}

        </div>

      </form>

    </div>
  );
}