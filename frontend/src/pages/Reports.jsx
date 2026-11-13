import { useEffect, useState } from "react";
import { api } from "../api.js";
import BarChart from "../components/BarChart.jsx";
import { downloadFile } from "../files.js";
import { compactMoney, money } from "../format.js";

const EXPORTS = [["purchase_orders", "Purchase orders"], ["invoices", "Invoices"], ["vendor_performance", "Vendor performance"], ["monthly", "Monthly trend"]];
const inr = (v, axis) => (axis ? compactMoney(v) : money(v));
const hours = (h) => (h == null ? "-" : h < 1 ? `${Math.round(h * 60)} min` : `${h} h`);

function Stat({ label, value, note }) {
  return <div className="card stat"><span>{label}</span><strong>{value}</strong>{note && <span className="muted">{note}</span>}</div>;
}

export default function Reports() {
  const [range, setRange] = useState({ from: "", to: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(r) {
    setError(""); setBusy(true);
    try {
      const qs = new URLSearchParams();
      if (r.from) qs.set("from", r.from);
      if (r.to) qs.set("to", r.to);
      const d = await api(`/reports/summary${qs.toString() ? `?${qs}` : ""}`);
      setData(d);
      setRange({ from: d.range.from, to: d.range.to });
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  useEffect(() => { load({ from: "", to: "" }); }, []);

  const exportCsv = (kind) => {
    const qs = new URLSearchParams({ kind, from: range.from, to: range.to });
    downloadFile(`/reports/export?${qs}`, `vendorbridge-${kind.replaceAll("_", "-")}.csv`).catch((e) => setError(e.message));
  };

  if (!data) return error ? <><h1>Reports and analytics</h1><p className="error" role="alert">{error}</p><button onClick={() => load({ from: "", to: "" })}>Try again</button></> : <p className="center">Loading...</p>;
  const k = data.kpis;

  return (
    <>
      <h1>Reports and analytics</h1>
      <p className="lead">Procurement insights from your saved records, {data.range.from} to {data.range.to}</p>
      {error && <p className="error" role="alert">{error}</p>}

      <form className="toolbar" onSubmit={(e) => { e.preventDefault(); load(range); }}>
        <label>From<input type="date" value={range.from} max={range.to} onChange={(e) => setRange({ ...range, from: e.target.value })} required /></label>
        <label>To<input type="date" value={range.to} min={range.from} onChange={(e) => setRange({ ...range, to: e.target.value })} required /></label>
        <button type="submit" className="btn primary" disabled={busy}>{busy ? "Loading..." : "Apply"}</button>
        <button type="button" onClick={() => load({ from: "", to: "" })} disabled={busy}>Last 6 months</button>
      </form>

      {!data.has_data && <p className="notice warn-box" role="status">There is no procurement activity in this date range. Try a wider range.</p>}

      <h2 className="sec">Spend and orders</h2>
      <div className="grid">
        <Stat label="Total spend" value={money(k.total_spend)} note="Purchase orders, incl. GST" />
        <Stat label="Purchase orders" value={k.po_count} note={`Average ${money(k.avg_po_value)}`} />
        <Stat label="RFQs created" value={k.rfqs_created} note={`${k.rfqs_sent} sent to vendors`} />
        <Stat label="Quotations received" value={k.quotations_submitted} note={`${k.avg_quotes_per_rfq} per sent RFQ`} />
      </div>

      <h2 className="sec">Monthly trend</h2>
      <div className="two-col">
        <section className="card form-section"><h3>Spend per month (INR)</h3><BarChart title="Monthly spend" data={data.monthly.map((m) => ({ label: m.label.replace(" 20", " '"), value: m.spend }))} format={inr} /></section>
        <section className="card form-section"><h3>Purchase orders per month</h3><BarChart title="Purchase orders per month" data={data.monthly.map((m) => ({ label: m.label.replace(" 20", " '"), value: m.pos }))} color="#25601b" /></section>
      </div>

      <h2 className="sec">Approvals and invoices</h2>
      <div className="grid">
        <Stat label="Approved" value={k.approvals_approved} note={`${k.approvals_rejected} rejected, ${k.approvals_pending} pending`} />
        <Stat label="Approval turnaround" value={hours(k.avg_approval_hours)} note="Submission to final approval" />
        <Stat label="Invoiced" value={money(k.invoiced_total)} note={`${k.invoice_count} invoice${k.invoice_count === 1 ? "" : "s"}`} />
        <Stat label="Outstanding" value={money(k.outstanding_total)} note={`Paid ${money(k.paid_total)} \u00b7 overdue ${money(k.overdue_total)} (${k.overdue_count})`} />
      </div>

      <h2 className="sec">Spend by category</h2>
      <section className="card form-section">
        {data.spend_by_category.length === 0 ? <p className="muted">No purchase orders in this range.</p> : (
          <ul className="hbars">
            {data.spend_by_category.map((c) => (
              <li key={c.category}>
                <span>{c.category}</span>
                <span className="bar"><i style={{ width: `${(c.spend / data.spend_by_category[0].spend) * 100}%` }} /></span>
                <span>{money(c.spend)} <span className="muted">({c.po_count} PO)</span></span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <h2 className="sec">Vendor performance</h2>
      {data.vendors.length === 0 ? <div className="card empty"><p>No vendor activity in this range.</p></div> : (
        <div className="compare-wrap">
          <table>
            <thead><tr><th>Vendor</th><th>Rating</th><th>RFQs invited</th><th>Quoted</th><th>Response rate</th><th>Lowest-price wins</th><th>Avg delivery</th><th>POs</th><th>PO value</th></tr></thead>
            <tbody>
              {data.vendors.map((v) => (
                <tr key={v.vendor_id}>
                  <td><strong>{v.vendor}</strong></td>
                  <td>{v.rating > 0 ? `\u2605 ${v.rating.toFixed(1)}` : "-"}</td>
                  <td>{v.invited}</td><td>{v.quoted}</td>
                  <td>{v.response_rate == null ? "-" : `${v.response_rate}%`}</td>
                  <td>{v.lowest_wins}</td>
                  <td>{v.avg_delivery_days == null ? "-" : `${v.avg_delivery_days} days`}</td>
                  <td>{v.po_count}</td><td>{money(v.po_value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="sec">Export (CSV)</h2>
      <div className="actions no-print">
        {EXPORTS.map(([kind, label]) => <button key={kind} onClick={() => exportCsv(kind)}>{label}</button>)}
      </div>

      <details className="card form-section">
        <summary>How these numbers are calculated</summary>
        <dl className="defs">{Object.entries(data.definitions).map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}</dl>
      </details>
    </>
  );
}