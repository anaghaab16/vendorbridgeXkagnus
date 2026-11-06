import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate, money } from "../format.js";

export default function Invoices() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/invoices").then(setRows).catch((e) => { setError(e.message); setRows([]); }); }, []);

  return (
    <>
      <h1>Invoices</h1>
      <p className="lead">Invoices generated from purchase orders</p>
      {error && <p className="error" role="alert">{error}</p>}
      {rows === null ? <p className="center">Loading...</p> : rows.length === 0 && !error ? (
        <div className="card empty"><h3>No invoices yet</h3><p>Open a purchase order and choose "Generate invoice".</p></div>
      ) : (
        <table>
          <thead><tr><th>Invoice no.</th><th>PO</th><th>Vendor</th><th>Date</th><th>Due</th><th>Total</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.map((i) => (
              <tr key={i.id}>
                <td className="nowrap"><strong>{i.invoice_number}</strong></td>
                <td>{i.po_number}</td>
                <td>{i.vendor_name}</td>
                <td>{formatDate(i.invoice_date)}</td>
                <td>{formatDate(i.due_date)}{i.is_overdue && <div className="muted warn">overdue</div>}</td>
                <td>{money(i.grand_total)}</td>
                <td><StatusPill status={i.status} /></td>
                <td className="row-actions"><Link className="btn" to={`/invoices/${i.id}`}>View</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}