import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate, money, ratingLabel } from "../format.js";

const when = (iso) => (iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : "");

export default function ApprovalDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [a, setA] = useState(null);
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canCreatePO = ["admin", "procurement_officer"].includes(user.role);

  useEffect(() => { api(`/approvals/${id}`).then(setA).catch((e) => setError(e.message)); }, [id]);

  async function decide(decision) {
    setError(""); setBusy(true);
    try {
      setA(await api(`/approvals/${id}/decision`, { method: "POST", body: { decision, remarks } }));
      setRemarks("");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function createPO() {
    setError(""); setBusy(true);
    try {
      const po = await api("/purchase-orders", { method: "POST", body: { approval_id: Number(id) } });
      navigate(`/purchase-orders/${po.id}`);
    } catch (e) { setError(e.message); setBusy(false); }
  }

  if (!a) return error ? <p className="error" role="alert">{error}</p> : <p className="center">Loading...</p>;
  const q = a.quotation;

  return (
    <>
      <div className="page-head"><h1>Approval workflow</h1><Link className="btn" to="/approvals">Back</Link></div>
      <p className="lead"><strong>{a.rfq_number}</strong> &middot; {a.rfq_title} &middot; {a.vendor_name} &middot; {money(a.total)} &nbsp;<StatusPill status={a.status} /></p>
      {error && <p className="error" role="alert">{error}</p>}

      <ol className="stepper" aria-label="Approval progress">
        {a.timeline.map((t, n) => (
          <li key={t.key} className={t.status}>
            <span className="dot">{t.status === "done" ? "\u2713" : t.status === "rejected" ? "\u2715" : n + 1}</span>
            <span className="step-label">{t.label}</span>
          </li>
        ))}
      </ol>

      <div className="two-col">
        <section className="card form-section">
          <h3>Approval chain</h3>
          {a.timeline.map((t) => (
            <div className={`chain ${t.status}`} key={t.key}>
              <strong>{t.label}</strong> <span className={`pill ${t.status === "done" ? "approved" : t.status === "rejected" ? "rejected" : "draft"}`}>{t.status}</span>
              <div className="muted">
                {t.actor ? `${t.actor}${t.at ? ` \u00b7 ${when(t.at)}` : ""}` : t.status === "current" ? "Waiting for a decision" : ""}
              </div>
              {t.key !== "po" && t.remarks && <div className="remark">&ldquo;{t.remarks}&rdquo;</div>}
              {t.key === "po" && t.remarks && <div className="muted">{t.remarks}</div>}
            </div>
          ))}

          {a.can_decide ? (
            <div className="decision">
              <label>Approval remarks
                <textarea rows={3} maxLength={1000} value={remarks} onChange={(e) => setRemarks(e.target.value)}
                  placeholder="Add your comments or conditions. Required if you reject." />
              </label>
              <div className="actions">
                <button className="btn primary" disabled={busy} onClick={() => decide("approve")}>Approve</button>
                <button className="danger" disabled={busy} onClick={() => decide("reject")}>Reject</button>
              </div>
            </div>
          ) : (
            a.decision_note && a.status.startsWith("awaiting") && <p className="muted">{a.decision_note}</p>
          )}

          {a.status === "approved" && (
            a.po_id ? <p className="notice">Purchase order {a.po_number} created. <Link className="lk" to={`/purchase-orders/${a.po_id}`}>Open it</Link></p>
              : canCreatePO && <div className="actions"><button className="btn primary" disabled={busy} onClick={createPO}>Generate purchase order</button></div>
          )}
        </section>

        <section className="card form-section">
          <h3>Quotation summary</h3>
          <dl className="facts">
            <div><dt>Vendor</dt><dd>{q.vendor_name}</dd></div>
            <div><dt>Rating</dt><dd>{ratingLabel(q.rating)}</dd></div>
            <div><dt>Delivery</dt><dd>{q.delivery_days} days</dd></div>
            <div><dt>Payment terms</dt><dd>{q.payment_terms || "-"}</dd></div>
            <div><dt>Submitted</dt><dd>{formatDate(q.submitted_at)}</dd></div>
          </dl>
          <table>
            <thead><tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Total</th></tr></thead>
            <tbody>{q.lines.map((l) => <tr key={l.rfq_item_id}><td>{l.item_name}</td><td>{l.quantity} {l.unit}</td><td>{money(l.unit_price)}</td><td>{money(l.line_total)}</td></tr>)}</tbody>
          </table>
          <dl className="facts">
            <div><dt>Subtotal</dt><dd>{money(q.subtotal)}</dd></div>
            <div><dt>GST ({q.gst_percent}%)</dt><dd>{money(q.gst_amount)}</dd></div>
            <div><dt><strong>Grand total</strong></dt><dd><strong>{money(q.total)}</strong></dd></div>
          </dl>
          {q.notes && <p className="muted">Vendor notes: {q.notes}</p>}
        </section>
      </div>
    </>
  );
}