import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiError } from '../services/api';
import { Loading, ErrorBox, NotSpecified } from '../components/Common';

export function PolicyList() {
  const [policies, setPolicies] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.listPolicies().then(setPolicies).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  if (error) return <ErrorBox message={error} />;
  if (!policies) return <Loading label="Loading policies…" />;

  return (
    <div>
      <h1>Policies</h1>
      <p className="page-subtitle">Every real policy version currently in the dataset.</p>
      <table>
        <thead>
          <tr><th>Insurer</th><th>Product</th><th>Policy Version</th><th>UIN</th><th>Status</th></tr>
        </thead>
        <tbody>
          {policies.flatMap(p => p.versions.map(v => (
            <tr key={v.policy_version_id} className="clickable">
              <td>{p.insurer}</td>
              <td>{p.product}</td>
              <td><Link to={`/policies/${p.policy_id}?version=${v.policy_version_id}`}>{v.policy_version_id}</Link></td>
              <td>{v.uin}{v.uin_conflict_flag ? ' ⚠️ UIN CONFLICT' : ''}</td>
              <td>{v.status}</td>
            </tr>
          )))}
        </tbody>
      </table>
    </div>
  );
}

export function PolicyDetail() {
  const { policyId } = useParams();
  const [rulesData, setRulesData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getPolicyRules(policyId).then(setRulesData).catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [policyId]);

  if (error) return <ErrorBox message={error} />;
  if (!rulesData) return <Loading label="Loading policy rules…" />;

  return (
    <div>
      <p><Link to="/policies">&larr; Back to policies</Link></p>
      <h1>Policy Rules</h1>
      {rulesData.map(group => (
        <div key={group.policy_version_id}>
          <h2>{group.policy_version_id} ({group.rules.length} rules)</h2>
          <table>
            <thead>
              <tr>
                <th>Rule ID</th><th>Category</th><th>Value/Condition</th>
                <th>Review Status</th><th>Source Document</th><th>Page</th><th>Provenance</th>
              </tr>
            </thead>
            <tbody>
              {group.rules.map(r => (
                <tr key={r.candidate_id}>
                  <td>{r.candidate_id}</td>
                  <td>{r.rule_type}</td>
                  <td>{r.value} {r.unit !== 'NOT_APPLICABLE' ? r.unit : ''}</td>
                  <td>{r.review_status}</td>
                  <td>{r.source_document || <NotSpecified />}</td>
                  <td>{r.source_page || <NotSpecified />}</td>
                  <td>{r.provenance || <NotSpecified />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
