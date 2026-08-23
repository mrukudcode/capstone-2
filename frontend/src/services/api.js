// Central API service. Every backend call goes through here.
// Uses the REAL FastAPI backend (root-level routes) -- no mocked data
// anywhere in this file or the app.

const BASE = ''; // same-origin, proxied to the backend in dev (see vite.config.js)

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (networkErr) {
    throw new ApiError(
      `Cannot reach the backend API. Is it running? (${networkErr.message})`,
      0,
    );
  }

  let body = null;
  const text = await res.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const detail = (body && body.detail) ? body.detail : `HTTP ${res.status}`;
    throw new ApiError(detail, res.status, body);
  }
  return body;
}

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export const api = {
  health: () => request('/health'),
  listPolicies: () => request('/policies'),
  getPolicy: (policyId) => request(`/policies/${policyId}`),
  getPolicyRules: (policyId) => request(`/policies/${policyId}/rules`),
  getPolicySources: (policyId) => request(`/policies/${policyId}/sources`),
  getDocumentText: (documentId) => request(`/documents/${encodeURIComponent(documentId)}/text`),
  getRule: (candidateId) => request(`/rules/${encodeURIComponent(candidateId)}`),
  createClaim: (payload) => request('/claims', { method: 'POST', body: JSON.stringify(payload) }),
  listClaims: () => request('/claims'),
  getClaim: (claimId) => request(`/claims/${claimId}`),
    validateClaim: (claimId) => request(`/claims/${claimId}/validate`, { method: 'POST' }),
  getValidation: (claimId) => request(`/claims/${claimId}/validation`),
  askClaimQuestion: (claimId, question) => request(`/claims/${claimId}/questions`, {
    method: 'POST',
    body: JSON.stringify({ question }),
  }),
};

