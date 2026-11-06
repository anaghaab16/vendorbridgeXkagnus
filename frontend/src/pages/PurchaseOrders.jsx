import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate, money } from "../format.js";

export default function PurchaseOrders() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api("/purchase-orders").then(setRows).catch((e) => { setError(e.message); setRows([]); }); }, []);

  return (
    <>
      <h1>Purchase orders</h1>
      <p className="lead">Orders created from approved quotations</p>
      {error && <p className="error" role="alert">{error}</p>}
      {rows === null ? <p className="center">Loading...</p> : rows.length === 0 && !error ? (
        <div className="card empty"><h3>No purchase orders yet</h3><p>A purchase order appears here after a quotation is approved.</p></div>
      ) : (
        <table>
          <thead><tr><th>PO no.</th><th>RFQ</th><th>Vendor</th><th>Date</th><th>Total</th><th>Status</th><th>Invoice</th><th></th></tr></thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td className="nowrap"><strong>{p.po_number}</strong></td>
                <td>{p.rfq_number}<div className="muted">{p.rfq_title}</div></td>
                <td>{p.vendor_name}</td>
                <td>{formatDate(p.po_date)}</td>
                <td>{money(p.grand_total)}</td>
                <td><StatusPill status={p.status} /></td>
                <td>{p.invoice_id ? <Link className="lk" to={`/invoices/${p.invoice_id}`}>{p.invoice_number}</Link> : <span className="muted">none</span>}</td>
                <td className="row-actions"><Link className="btn" to={`/purchase-orders/${p.id}`}>View</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}