import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { dateTime } from "../format.js";

const TYPES = [["", "All"], ["rfq", "RFQs"], ["quotation", "Quotations"], ["approval", "Approvals"], ["purchase_order", "Purchase orders"], ["invoice", "Invoices"], ["vendor", "Vendors"], ["user", "Users"]];
const PAGE = 50;
const LINKS = { rfq: (i) => `/rfqs/${i}`, approval: (i) => `/approvals/${i}`, purchase_order: (i) => `/purchase-orders/${i}`, invoice: (i) => `/invoices/${i}`, vendor: () => "/vendors" };

export default function Activity() {
  const { user } = useAuth();
  const [type, setType] = useState("");
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ownOnly = user.role === "procurement_officer";

  async function load(offset) {
    setError(""); setBusy(true);
    try {
      const page = await api(`/activity?limit=${PAGE}&offset=${offset}${type ? `&entity_type=${type}` : ""}`);
      setItems(offset === 0 ? page.items : [...items, ...page.items]);
      setTotal(page.total);
    } catch (e) { setError(e.message); if (offset === 0) setItems([]); } finally { setBusy(false); }
  }
  useEffect(() => { setItems(null); load(0); }, [type]);

  // group by calendar day, newest first
  const days = [];
  (items || []).forEach((i) => {
    const day = new Date(i.created_at).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    const last = days[days.length - 1];
    if (last && last.day === day) last.rows.push(i); else days.push({ day, rows: [i] });
  });

  return (
    <>
      <h1>Activity and logs</h1>
      <p className="lead">Procurement audit trail. Records are written by the system and cannot be edited or deleted.{ownOnly && " You can see your own actions."}</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="chips">
        {TYPES.map(([v, label]) => <button key={v} className={`chip ${type === v ? "on" : ""}`} onClick={() => setType(v)}>{label}</button>)}
      </div>

      {items === null ? <p className="center">Loading...</p> : items.length === 0 && !error ? (
        <div className="card empty"><h3>No activity yet</h3><p>Actions such as creating an RFQ or approving a quotation appear here.</p></div>
      ) : (
        <>
          {days.map((d) => (
            <section key={d.day} className="day">
              <h3>{d.day}</h3>
              <ol className="timeline">
                {d.rows.map((i) => {
                  const link = LINKS[i.entity_type]?.(i.entity_id);
                  return (
                    <li key={i.id}>
                      <span className={`tl-dot ${i.entity_type}`} aria-hidden="true" />
                      <div>
                        <div>{i.message}</div>
                        <div className="muted">
                          {i.actor_name}{i.actor_role && ` (${i.actor_role.replaceAll("_", " ")})`} &middot; {dateTime(i.created_at)} &middot; <code>{i.action}</code>
                          {link && i.entity_label && <> &middot; <Link className="lk" to={link}>{i.entity_label}</Link></>}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
          <p className="muted">Showing {items.length} of {total}</p>
          {items.length < total && <button disabled={busy} onClick={() => load(items.length)}>{busy ? "Loading..." : "Load more"}</button>}
        </>
      )}
    </>
  );
}