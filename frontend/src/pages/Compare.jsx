import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { formatDate, money, ratingLabel } from "../format.js";

const SORTS = {
  price: ["Lowest price", (a, b) => a.total - b.total],
  delivery: ["Fastest delivery", (a, b) => (a.delivery_days ?? 1e9) - (b.delivery_days ?? 1e9)],
  rating: ["Highest rating", (a, b) => b.rating - a.rating],
};

export default function Compare() {
  const { id } = useParams();
  const { user } = useAuth();
  const canSelect = ["admin", "procurement_officer"].includes(user.role);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [sort, setSort] = useState("price");
  const [minRating, setMinRating] = useState("0");
  const [maxDays, setMaxDays] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api(`/rfqs/${id}/comparison`).then(setData).catch((e) => setError(e.message));
  }, [id]);

  if (!data) return error ? <p className="error" role="alert">{error}</p> : <p className="center">Loading...</p>;

  const quotes = data.quotes
    .filter((q) => q.rating >= Number(minRating))
    .filter((q) => !maxDays || (q.delivery_days ?? 1e9) <= Number(maxDays))
    .sort(SORTS[sort][1]);
  const cls = (flag) => (flag ? "best" : "");
  const canPick = canSelect && (data.status === "sent" || data.status === "closed");

  async function select(quotationId) {
    setError(""); setBusy(true);
    try {
      setData(await api(`/rfqs/${id}/selected-quotation`, { method: "PUT", body: { quotation_id: quotationId } }));
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  return (
    <>
      <div className="page-head"><h1>Quotation comparison</h1><Link className="btn" to={`/rfqs/${id}`}>Back to RFQ</Link></div>
      <p className="lead"><strong>{data.rfq_number}</strong> &middot; {data.title} &middot; deadline {formatDate(data.deadline)} &middot; {data.quotes.length} quotation{data.quotes.length === 1 ? "" : "s"} received</p>
      {error && <p className="error" role="alert">{error}</p>}
      {data.waiting.length > 0 && <p className="muted">Waiting for: {data.waiting.join(", ")}</p>}

      {data.quotes.length === 0 ? (
        <div className="card empty"><h3>No submitted quotations yet</h3><p>Vendors' drafts are not shown. Check back after they submit.</p></div>
      ) : (
        <>
          <div className="toolbar">
            <label>Sort by
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                {Object.entries(SORTS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
              </select></label>
            <label>Minimum rating
              <select value={minRating} onChange={(e) => setMinRating(e.target.value)}>
                <option value="0">Any</option><option value="3">3.0 and above</option><option value="4">4.0 and above</option><option value="4.5">4.5 and above</option>
              </select></label>
            <label>Max delivery (days)
              <input type="number" min="1" value={maxDays} onChange={(e) => setMaxDays(e.target.value)} placeholder="Any" /></label>
          </div>

          {quotes.length === 0 ? (
            <div className="card empty"><h3>No quotations match these filters</h3></div>
          ) : (
            <div className="compare-wrap">
              <table className="compare">
                <thead>
                  <tr>
                    <th>Criteria</th>
                    {quotes.map((q) => (
                      <th key={q.vendor_id} className={`${cls(q.is_lowest)} ${q.is_selected ? "picked" : ""}`}>
                        {q.vendor_name}
                        <div>{q.is_lowest && <span className="tag good">Lowest price</span>}{q.is_fastest && <span className="tag">Fastest</span>}{q.is_selected && <span className="tag sel">Selected</span>}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="strong"><th>Grand total</th>{quotes.map((q) => <td key={q.vendor_id} className={cls(q.is_lowest)}>{money(q.total)}</td>)}</tr>
                  <tr><th>Subtotal</th>{quotes.map((q) => <td key={q.vendor_id}>{money(q.subtotal)}</td>)}</tr>
                  <tr><th>GST</th>{quotes.map((q) => <td key={q.vendor_id}>{money(q.gst_amount)} ({q.gst_percent}%)</td>)}</tr>
                  <tr><th>Delivery</th>{quotes.map((q) => <td key={q.vendor_id} className={cls(q.is_fastest)}>{q.delivery_days} days</td>)}</tr>
                  <tr><th>Vendor rating</th>{quotes.map((q) => <td key={q.vendor_id}>{ratingLabel(q.rating)}</td>)}</tr>
                  <tr><th>Payment terms</th>{quotes.map((q) => <td key={q.vendor_id}>{q.payment_terms || "-"}</td>)}</tr>
                  {data.items.map((it) => (
                    <tr key={it.id}>
                      <th>{it.item_name}<div className="muted">{it.quantity} {it.unit}</div></th>
                      {quotes.map((q) => {
                        const line = q.lines.find((l) => l.rfq_item_id === it.id);
                        return <td key={q.vendor_id}>{money(line?.unit_price)} each<div className="muted">{money(line?.line_total)}</div></td>;
                      })}
                    </tr>
                  ))}
                  <tr><th>Notes</th>{quotes.map((q) => <td key={q.vendor_id}>{q.notes || "-"}</td>)}</tr>
                  {canPick && (
                    <tr><th>Selection</th>{quotes.map((q) => (
                      <td key={q.vendor_id}>
                        {q.is_selected
                          ? <button type="button" disabled={busy} onClick={() => select(null)}>Clear selection</button>
                          : <button type="button" className="btn primary" disabled={busy} onClick={() => select(q.quotation_id)}>Select this quotation</button>}
                      </td>))}
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted">Lowest price and fastest delivery are worked out across all submitted quotations, not only the ones shown. Selecting a quotation marks it for the approval step; it does not approve it.</p>
        </>
      )}
    </>
  );
}