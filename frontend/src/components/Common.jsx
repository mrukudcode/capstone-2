export function SeverityBadge({ severity }) {
  const cls = `badge badge-${(severity || '').toLowerCase()}`;
  return <span className={cls}>{severity}</span>;
}

export function OverallBanner({ result }) {
  const labels = {
    SUBMISSION_READY: 'Submission Ready',
    HUMAN_REVIEW_NEEDED: 'Human Review Needed',
    FIX_BEFORE_SUBMISSION: 'Fix Before Submission',
  };
  const cls = `overall-banner overall-${(result || '').toLowerCase()}`;
  return <div className={cls}>{labels[result] || result}</div>;
}

export function Loading({ label = 'Loading…' }) {
  return <div className="loading-box">{label}</div>;
}

export function ErrorBox({ message }) {
  if (!message) return null;
  return <div className="error-box">{message}</div>;
}

export function NotSpecified() {
  return <span className="not-specified">Not specified in source</span>;
}
