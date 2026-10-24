import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

function Card({ label, value }) {
  return <div className="card stat"><span>{label}</span><strong>{value}</strong></div>;
}

export default function Dashboard() {
  const { user } = useAuth();
  const [vendors, setVendors] = useState(null);
  const canSeeVendors = ["admin", "manager", "procurement_officer"].includes(user.role);

  useEffect(() => { if (canSeeVendors) api("/vendors").then(setVendors).catch(() => setVendors([])); }, [canSeeVendors]);

  const count = (s) => (vendors ? vendors.filter((v) => v.status === s).length : "-");

  return (
    <>
      <h1>Welcome, {user.name}</h1>
      <div className="grid">
        <Card label="Total vendors" value={vendors ? vendors.length : "-"} />
        <Card label="Active vendors" value={count("active")} />
        <Card label="Pending vendors" value={count("pending")} />
        <Card label="Open purchase orders" value="-" />
      </div>
      {canSeeVendors && (
        <div className="actions">
          <Link className="btn" to="/vendors">Manage vendors</Link>
        </div>
      )}
      <div className="card empty">
        <h3>Purchase orders and approvals</h3>
        <p>No data yet. These modules arrive in the next weeks.</p>
      </div>
    </>
  );
}
