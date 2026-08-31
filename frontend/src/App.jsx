import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import NewClaim from './pages/NewClaim';
import ClaimsHistory from './pages/ClaimsHistory';
import ClaimDetail from './pages/ClaimDetail';
import RuleEvidence from './pages/RuleEvidence';
import { PolicyList, PolicyDetail } from './pages/PolicyBrowser';
import PolicySourceViewer from './pages/PolicySourceViewer';
import Documentation from './pages/Documentation';
import PolicyUpload from './pages/PolicyUpload';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/claims/new" element={<NewClaim />} />
        <Route path="/claims" element={<ClaimsHistory />} />
        <Route path="/claims/:claimId" element={<ClaimDetail />} />
        <Route path="/claims/:claimId/rules/:ruleId" element={<RuleEvidence />} />
        <Route path="/policies" element={<PolicyList />} />
        <Route path="/policies/:policyId" element={<PolicyDetail />} />
        <Route path="/policies/upload" element={<PolicyUpload />} />
        <Route path="/policy-source-viewer" element={<PolicySourceViewer />} />
        <Route path="/documentation" element={<Documentation />} />
      </Routes>
    </Layout>
  );
}
