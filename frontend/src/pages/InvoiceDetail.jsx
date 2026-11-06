import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import DocumentSheet from "../components/DocumentSheet.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { downloadFile } from "../files.js";
import { formatDate } from "../format.js";

export default function InvoiceDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [inv, setInv] = useState(null);
  const [to, setTo] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const isStaff = user.role !== "vendor";
  const canPay = ["admin", "manager"].includes(user.role);

  const load = () => api(`/invoices/${id}`).then((d) => { setInv(d); setTo((t) => t || d.vendor.email || ""); }).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [id]);

  async function run(fn) {
    setError(""); setNotice(""); setBusy(true);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  const download = () => run(() => downloadFile(`/invoices/${id}/pdf`, `${inv.invoice_number}.pdf`));
  const sendEmail = (e) => { e.preventDefault(); run(async () => { const r = await api(`/invoices/${id}/email`, { method: "POST", body: { to: to || null } }); setNotice(r.message); await load(); }); };
  const pay = () => { if (window.confirm("Mark this invoice as paid?")) run(async () => { setInv(await api(`/invoices/${id}/mark-paid`, { method: "PATCH" })); setNotice("Invoice marked as paid."); }); };

  if (!inv) return error ? <p className="error" role="alert">{error}</p> : <p className="center">Loading...</p>;

  return (
    <>
      <div className="page-head no-print"><h1>Invoice</h1><Link className="btn" to="/invoices">Back</Link></div>
      {notice && <p className="notice no-print" role="status">{notice}</p>}
      {error && <p className="error no-print" role="alert">{error}</p>}

      <div className="actions no-print">
        <button className="btn primary" disabled={busy} onClick={download}>Download PDF</button>
        <button onClick={() => window.print()}>Print</button>
        {canPay && inv.status === "pending_payment" && <button disabled={busy} onClick={pay}>Mark as paid</button>}
        <Link className="btn" to={`/purchase-orders/${inv.po_id}`}>Open PO {inv.po_number}</Link>
      </div>

      {isStaff && (
        <form className="card form-section no-print email-box" onSubmit={sendEmail}>
          <h3>Email invoice</h3>
          {!inv.email_enabled && <p className="muted warn">Email is not set up on the server yet, so sending will fail. Add the SMTP settings to the backend .env file.</p>}
          <div className="item-row email-row">
            <input type="email" aria-label="Send to" placeholder="vendor@company.com" value={to} onChange={(e) => setTo(e.target.value)} required />
            <button type="submit" className="btn primary" disabled={busy}>{busy ? "Sending..." : "Send invoice"}</button>
          </div>
          {inv.emails.length > 0 && (
            <ul className="mail-log">
              {inv.emails.slice().reverse().map((m, n) => (
                <li key={n} className={m.ok ? "ok" : "bad"}>{m.ok ? "Sent to" : "Failed to send to"} {m.to_email} <span className="muted">{new Date(m.created_at).toLocaleString("en-IN")}</span></li>
              ))}
            </ul>
          )}
        </form>
      )}

      <DocumentSheet
        title="Tax invoice" number={inv.invoice_number}
        meta={[["Invoice date", formatDate(inv.invoice_date)], ["Due date", formatDate(inv.due_date)], ["PO", inv.po_number],
               ["RFQ", inv.rfq_number || "-"], ["Payment terms", inv.payment_terms || "-"],
               ["Status", <StatusPill key="s" status={inv.is_overdue ? "overdue" : inv.status} />]]}
        buyer={inv.buyer} vendor={inv.vendor} items={inv.items} totals={inv.totals}
        footer={inv.paid_at ? `Paid on ${formatDate(inv.paid_at)}.` : "This is a computer generated invoice."}
      />
    </>
  );
}