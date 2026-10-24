import { NavLink } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const STAFF = ["admin", "manager", "procurement_officer"];
// pages that exist in the mockup but are not built yet
const LATER = ["RFQ's", "Quotations", "Approvals", "Purchase orders", "Invoices", "Reports", "Activity"];

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const canSeeVendors = STAFF.includes(user.role);

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 17h18M5 17V9m14 8V9M5 9a7 7 0 0 1 14 0" /></svg>
          </span>
          VendorBridge
        </div>
        <div className="user-box">
          <span className="avatar" aria-hidden="true">{user.name?.[0]?.toUpperCase()}</span>
          <span className="user-name">{user.name}</span>
          <span className="badge">{user.role.replaceAll("_", " ")}</span>
          <button type="button" onClick={logout}>Logout</button>
        </div>
      </header>

      <div className="body">
        <aside className="sidebar">
          <nav aria-label="Main">
            <NavLink to="/" end>Dashboard</NavLink>
            {canSeeVendors && <NavLink to="/vendors">Vendors</NavLink>}
            {LATER.map((label) => (
              <span key={label} className="soon">{label}</span>
            ))}
          </nav>
        </aside>
        <main>{children}</main>
      </div>
    </div>
  );
}