import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate, money } from "../format.js";

function Card({ label, value, to }) {
  const body = <><span>{label}</span><strong>{value}</strong></>;
  return to ? <Link className="card stat stat-link" to={to}>{body}</Link> : <div className="card stat">{body}</div>;
}

export default function Dashboard() {
  const { user } = useAuth();
  const isVendor = user.role === "vendor";
  const canCreateRFQ = ["admin", "procurement_officer"].includes(user.role);
  const [data, setData] = useState(null); // null while loading
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    // each list comes from the server for this user's role; one failing does not blank the others
    const paths = isVendor
      ? { rfqs: "/my/rfqs", pos: "/purchase-orders", invoices: "/invoices" }
      : { vendors: "/vendors", rfqs: "/rfqs", approvals: "/approvals", pos: "/purchase-orders", invoices: "/invoices" };
    Promise.allSettled(Object.values(paths).map((p) => api(p))).then((results) => {
      const out = {};
      Object.keys(paths).forEach((k, i) => { out[k] = results[i].status === "fulfilled" ? results[i].value : null; });
      setFailed(results.some((r) => r.status === "rejected"));
      setData(out);
    });
  }, [isVendor]);

  const count = (list, test) => (list ? list.filter(test).length : "-");
  const d = data || {};
  const openPOs = count(d.pos, (p) => p.status !== "closed");
  const unpaid = count(d.invoices, (i) => i.status === "pending_payment");
  const overdue = count(d.invoices, (i) => i.is_overdue);

  return (
    <>
      <h1>Welcome, {user.name}</h1>
      <p className="lead">{isVendor ? "Your RFQs, orders and invoices" : "Today's overview"}</p>
      {failed && data && <p className="error" role="alert">Some figures could not be loaded. Refresh to try again.</p>}

      {data === null ? <p className="center">Loading...</p> : isVendor ? (
        <div className="grid">
          <Card label="Open RFQs to quote" value={count(d.rfqs, (r) => r.status === "sent" && !r.deadline_passed && r.my_quotation_status !== "submitted")} to="/my-rfqs" />
          <Card label="Quotations submitted" value={count(d.rfqs, (r) => r.my_quotation_status === "submitted")} to="/my-rfqs" />
          <Card label="Open purchase orders" value={openPOs} to="/purchase-orders" />
          <Card label="Unpaid invoices" value={unpaid} to="/invoices" />
        </div>
      ) : (
        <>
          <div className="grid">
            <Card label="Active RFQs" value={count(d.rfqs, (r) => r.status === "sent" && !r.deadline_passed)} to="/rfqs" />
            <Card label="Pending approvals" value={count(d.approvals, (a) => a.status.startsWith("awaiting"))} to="/approvals" />
            <Card label="Open purchase orders" value={openPOs} to="/purchase-orders" />
            <Card label="Overdue invoices" value={overdue} to="/invoices" />
          </div>
          <div className="grid">
            <Card label="Total vendors" value={count(d.vendors, () => true)} to="/vendors" />
            <Card label="Active vendors" value={count(d.vendors, (v) => v.status === "active")} to="/vendors" />
            <Card label="Pending vendors" value={count(d.vendors, (v) => v.status === "pending")} to="/vendors" />
          </div>
          <div className="actions">
            {canCreateRFQ && <Link className="btn primary" to="/rfqs/new">+ New RFQ</Link>}
            <Link className="btn" to="/vendors">Add vendor</Link>
            <Link className="btn" to="/invoices">View invoices</Link>
          </div>
        </>
      )}

      {data && (
        <section className="card form-section">
          <h3>Recent purchase orders</h3>
          {!d.pos || d.pos.length === 0 ? (
            <p className="muted">{d.pos ? "No purchase orders yet. One appears here after a quotation is approved." : "Purchase orders could not be loaded."}</p>
          ) : (
            <table>
              <thead><tr><th>PO no.</th><th>Vendor</th><th>Date</th><th>Total</th><th>Status</th></tr></thead>
              <tbody>
                {d.pos.slice(0, 5).map((p) => (
                  <tr key={p.id}>
                    <td><Link className="lk" to={`/purchase-orders/${p.id}`}>{p.po_number}</Link></td>
                    <td>{p.vendor_name}</td>
                    <td>{formatDate(p.po_date)}</td>
                    <td>{money(p.grand_total)}</td>
                    <td><StatusPill status={p.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </>
  );
}