import { NavLink } from 'react-router-dom';

export default function Layout({ children }) {
  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="brand">Indian Health Insurance Claim Validator</div>
        <div className="brand-subtitle">
          Explainable Pre-Submission Health Insurance Claim Rule Validator
        </div>
        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Dashboard</NavLink>
        <NavLink to="/claims/new" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>New Claim</NavLink>
        <NavLink to="/claims" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Claims</NavLink>
        <NavLink to="/policies" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Policies</NavLink>
        <NavLink to="/policy-source-viewer" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Policy Source Viewer</NavLink>
        <NavLink to="/documentation" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>Documentation</NavLink>
      </nav>
      <main className="main-content">
        <div className="disclaimer-banner">
          This system checks documented policy rules. It does not predict or
          guarantee the insurer's final adjudication decision.
        </div>
        {children}
      </main>
    </div>
  );
}
