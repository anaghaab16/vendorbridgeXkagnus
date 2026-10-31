import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { downloadFile } from "../files.js";
import { formatDate, money } from "../format.js";

export default function MyRFQDetail() {
  const { id } = useParams();
  const [d, setD] = useState(null);
  const [prices, setPrices] = useState({});
  const [gst, setGst] = useState("18");
  const [days, setDays] = useState("");
  const [terms, setTerms] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  function fill(data) {
    const q = data.quotation;
    const p = {};
    (q?.lines || []).forEach((l) => { if (l.unit_price != null) p[l.rfq_item_id] = String(l.unit_price); });
    setPrices(p);
    setGst(String(q?.gst_percent ?? 18));
    setDays(q?.delivery_days ? String(q.delivery_days) : "");
    setTerms(q?.payment_terms || "");
    setNotes(q?.notes || "");
  }

  useEffect(() => {
    api(`/my/rfqs/${id}`).then((data) => { setD(data); fill(data); }).catch((e) => setError(e.message));
  }, [id]);

  async function save(submit) {
    setError(""); setNotice(""); setBusy(true);
    try {
      await api(`/my/rfqs/${id}/quotation`, {
        method: "PUT",
        body: {
          items: d.items.filter((i) => prices[i.id] !== undefined && prices[i.id] !== "")
            .map((i) => ({ rfq_item_id: i.id, unit_price: Number(prices[i.id]) })),
          gst_percent: Number(gst || 0),
          delivery_days: days ? Number(days) : null,
          payment_terms: terms,
          notes,
          submit,
        },
      });
      const fresh = await api(`/my/rfqs/${id}`);
      setD(fresh); fill(fresh);
      setNotice(submit ? "Quotation submitted. You can change it until the deadline." : "Draft saved. The procurement team cannot see it until you submit.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!d) return error ? <p className="error" role="alert">{error}</p> : <p className="center">Loading...</p>;

  const subtotal = d.items.reduce((s, i) => s + Number(prices[i.id] || 0) * i.quantity, 0);
  const gstAmount = (subtotal * Number(gst || 0)) / 100;
  const submitted = d.quotation?.status === "submitted";
  const reason = d.status === "closed" ? "This RFQ is closed." : d.deadline_passed ? "The deadline has passed, so the quotation can no longer be changed." : "";

  return (
    <>
      <div className="page-head"><h1>{d.title}</h1><Link className="btn" to="/my-rfqs">Back</Link></div>
      <p className="lead"><strong>{d.rfq_number}</strong> &middot; {d.category} &middot; deadline {formatDate(d.deadline)} &middot; quoting as {d.vendor_name}</p>
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      {reason && <p className="notice warn-box" role="status">{reason}</p>}

      {d.description && <section className="card form-section"><h3>Description</h3><p>{d.description}</p></section>}
      {d.attachments.length > 0 && (
        <section className="card form-section"><h3>Attachments</h3>
          {d.attachments.map((a) => (
            <div className="file-row" key={a.id}>{a.file_name}
              <button type="button" onClick={() => downloadFile(`/rfqs/${d.id}/attachments/${a.id}`, a.file_name).catch((e) => setError(e.message))}>Download</button></div>
          ))}
        </section>
      )}

      <form className="card form-section" onSubmit={(e) => { e.preventDefault(); save(true); }}>
        <h3>Your quotation {submitted && <span className="pill submitted">submitted</span>}</h3>
        <fieldset disabled={!d.can_edit || busy} className="plain">
          <table>
            <thead><tr><th>Item</th><th>Quantity</th><th>Unit price (INR)</th><th>Total</th></tr></thead>
            <tbody>
              {d.items.map((i) => (
                <tr key={i.id}>
                  <td>{i.item_name}</td>
                  <td>{i.quantity} {i.unit}</td>
                  <td><input aria-label={`Unit price for ${i.item_name}`} type="number" min="0" step="any" value={prices[i.id] ?? ""}
                    onChange={(e) => setPrices({ ...prices, [i.id]: e.target.value })} /></td>
                  <td>{money(Number(prices[i.id] || 0) * i.quantity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="form-grid">
            <label>GST (%)<input type="number" min="0" max="100" step="any" value={gst} onChange={(e) => setGst(e.target.value)} /></label>
            <label>Delivery time (days)<input type="number" min="1" max="730" value={days} onChange={(e) => setDays(e.target.value)} /></label>
            <label>Payment terms<input value={terms} onChange={(e) => setTerms(e.target.value)} maxLength={120} placeholder="e.g. 30 days" /></label>
            <label className="wide">Notes<textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} /></label>
          </div>
          <div className="totals">
            <div>Subtotal <strong>{money(subtotal)}</strong></div>
            <div>GST ({gst || 0}%) <strong>{money(gstAmount)}</strong></div>
            <div className="grand">Grand total <strong>{money(subtotal + gstAmount)}</strong></div>
          </div>
        </fieldset>

        {d.can_edit && (
          <div className="actions">
            {!submitted && <button type="button" disabled={busy} onClick={() => save(false)}>Save draft</button>}
            <button type="submit" className="btn primary" disabled={busy}>{busy ? "Saving..." : submitted ? "Update quotation" : "Submit quotation"}</button>
          </div>
        )}
      </form>
    </>
  );
}