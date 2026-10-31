import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate } from "../format.js";

export default function MyRFQs() {
  const [rfqs, setRfqs] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/my/rfqs").then(setRfqs).catch((e) => { setError(e.message); setRfqs([]); });
  }, []);

  return (
    <>
      <h1>My RFQs</h1>
      <p className="lead">Requests for quotation assigned to you</p>
      {error && <p className="error" role="alert">{error}</p>}
      {rfqs === null ? <p className="center">Loading...</p> : rfqs.length === 0 && !error ? (
        <div className="card empty"><h3>No RFQs assigned yet</h3><p>When the procurement team sends you one, it will show up here.</p></div>
      ) : (
        <table>
          <thead><tr><th>RFQ no.</th><th>Title</th><th>Category</th><th>Deadline</th><th>RFQ</th><th>My quotation</th><th></th></tr></thead>
          <tbody>
            {rfqs.map((r) => (
              <tr key={r.id}>
                <td className="nowrap">{r.rfq_number}</td>
                <td><strong>{r.title}</strong></td>
                <td>{r.category}</td>
                <td>{formatDate(r.deadline)}{r.status === "sent" && r.deadline_passed && <div className="muted warn">deadline passed</div>}</td>
                <td><StatusPill status={r.status} /></td>
                <td>{r.my_quotation_status ? <span className={`pill ${r.my_quotation_status}`}>{r.my_quotation_status}</span> : <span className="muted">not quoted</span>}</td>
                <td className="row-actions"><Link className="btn" to={`/my-rfqs/${r.id}`}>Open</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}