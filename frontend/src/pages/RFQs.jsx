import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate } from "../format.js";

const FILTERS = ["all", "draft", "sent", "closed", "cancelled"];

export default function RFQs() {
  const { user } = useAuth();
  const canCreate = ["admin", "procurement_officer"].includes(user.role);
  const [rfqs, setRfqs] = useState(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    api("/rfqs").then(setRfqs).catch((e) => { setError(e.message); setRfqs([]); });
  }, []);

  const count = (s) => (rfqs || []).filter((r) => s === "all" || r.status === s).length;
  const shown = (rfqs || []).filter(
    (r) => (filter === "all" || r.status === filter) && `${r.title} ${r.category} ${r.rfq_number || ""}`.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <>
      <div className="page-head">
        <h1>RFQs</h1>
        {canCreate && <Link className="btn primary" to="/rfqs/new">+ New RFQ</Link>}
      </div>
      <p className="lead">Create requests for quotation and track vendor responses</p>
      {error && <p className="error" role="alert">{error}</p>}

      <input className="search" placeholder="Search by number, title or category..." value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips">
        {FILTERS.map((f) => (
          <button key={f} className={`chip ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>
            {f[0].toUpperCase() + f.slice(1)} ({count(f)})
          </button>
        ))}
      </div>

      {rfqs === null ? (
        <p className="center">Loading...</p>
      ) : shown.length === 0 ? (
        <div className="card empty"><h3>No RFQs found</h3><p>Click "+ New RFQ" to create one.</p></div>
      ) : (
        <table>
          <thead><tr><th>RFQ no.</th><th>Title</th><th>Category</th><th>Deadline</th><th>Status</th><th>Quotes</th><th></th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td className="nowrap">{r.rfq_number}</td>
                <td><strong>{r.title}</strong><div className="muted">{r.item_count} item{r.item_count === 1 ? "" : "s"}</div></td>
                <td>{r.category}</td>
                <td>{formatDate(r.deadline)}{r.status === "sent" && r.deadline_passed && <div className="muted warn">deadline passed</div>}</td>
                <td><StatusPill status={r.status} />{r.selected_vendor_name && <div className="muted">Selected: {r.selected_vendor_name}</div>}</td>
                <td>{r.quote_count} of {r.vendor_count}</td>
                <td className="row-actions"><Link className="btn" to={`/rfqs/${r.id}`}>View</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}