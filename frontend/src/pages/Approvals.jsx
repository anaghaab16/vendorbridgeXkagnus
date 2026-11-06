import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate, money } from "../format.js";

const FILTERS = ["all", "awaiting_l1", "awaiting_l2", "approved", "rejected"];
const label = (f) => (f === "all" ? "All" : f.replace("awaiting_l", "Awaiting L").replace(/^./, (c) => c.toUpperCase()));

export default function Approvals() {
  const [rows, setRows] = useState(null);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/approvals").then(setRows).catch((e) => { setError(e.message); setRows([]); });
  }, []);

  const count = (f) => (rows || []).filter((r) => f === "all" || r.status === f).length;
  const shown = (rows || []).filter((r) => filter === "all" || r.status === filter);

  return (
    <>
      <h1>Approvals</h1>
      <p className="lead">Selected quotations waiting for review, and past decisions</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="chips">
        {FILTERS.map((f) => (
          <button key={f} className={`chip ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>{label(f)} ({count(f)})</button>
        ))}
      </div>

      {rows === null ? <p className="center">Loading...</p> : shown.length === 0 ? (
        <div className="card empty"><h3>No approval requests</h3><p>An officer sends a quotation here after selecting it on the comparison screen.</p></div>
      ) : (
        <table>
          <thead><tr><th>RFQ</th><th>Vendor</th><th>Total</th><th>Status</th><th>Requested by</th><th>Date</th><th></th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td><strong>{r.rfq_number}</strong><div className="muted">{r.rfq_title}</div></td>
                <td>{r.vendor_name}</td>
                <td>{money(r.total)}</td>
                <td><StatusPill status={r.status} /><div className="muted">{r.step_label}</div></td>
                <td>{r.requested_by_name}</td>
                <td>{formatDate(r.created_at)}</td>
                <td className="row-actions"><Link className="btn" to={`/approvals/${r.id}`}>Review</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}