import { money } from "../format.js";

function Party({ label, p }) {
  return (
    <div>
      <h4>{label}</h4>
      <strong>{p.name}</strong>
      {p.address && <div>{p.address}</div>}
      {p.gstin && <div>GSTIN: {p.gstin}</div>}
      {p.contact && <div>Phone: {p.contact}</div>}
      {p.email && <div>{p.email}</div>}
    </div>
  );
}

// The printable layout shared by purchase orders and invoices
export default function DocumentSheet({ title, number, meta, buyer, vendor, items, totals, footer }) {
  const half = totals.gst_percent / 2;
  return (
    <article className="sheet">
      <header className="sheet-head">
        <div><h2>{title}</h2><p className="sheet-no">{number}</p></div>
        <dl className="sheet-meta">
          {meta.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
        </dl>
      </header>

      <div className="sheet-parties"><Party label="Bill to" p={buyer} /><Party label="Vendor" p={vendor} /></div>

      <table className="sheet-items">
        <thead><tr><th>Item</th><th className="num">Qty</th><th className="num">Unit price</th><th className="num">Total</th></tr></thead>
        <tbody>
          {items.map((i, n) => (
            <tr key={n}>
              <td>{i.item_name}</td>
              <td className="num">{i.quantity} {i.unit}</td>
              <td className="num">{money(i.unit_price)}</td>
              <td className="num">{money(i.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <dl className="sheet-totals">
        <div><dt>Subtotal</dt><dd>{money(totals.subtotal)}</dd></div>
        {totals.igst > 0
          ? <div><dt>IGST ({totals.gst_percent}%)</dt><dd>{money(totals.igst)}</dd></div>
          : <>
              <div><dt>CGST ({half}%)</dt><dd>{money(totals.cgst)}</dd></div>
              <div><dt>SGST ({half}%)</dt><dd>{money(totals.sgst)}</dd></div>
            </>}
        <div className="grand"><dt>Grand total</dt><dd>{money(totals.grand_total)}</dd></div>
      </dl>
      {footer && <p className="muted">{footer}</p>}
    </article>
  );
}