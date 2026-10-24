import "./Onboarding.css";

const sampleOrders = [
  { id: "PO-0142", vendor: "Arden Packaging", status: "Approved" },
  { id: "PO-0143", vendor: "Kestrel Logistics", status: "In review" },
  { id: "PO-0144", vendor: "Maple & Co. Stationery", status: "Draft" },
];

// Shared shell: form on the left (children), product panel on the right.
export default function AuthLayout({ children }) {
  return (
    <div className="ob-page">
      <div className="ob-shell">
        <div className="ob-inner">
          {children}
          <aside className="ob-visual" aria-hidden="true">
            <div className="glass float-a" style={{ left: 52, top: 74, width: 250 }}>
              <small>Vendor onboarding</small>
              <div style={{ fontWeight: 600 }}>3 of 4 steps</div>
              <div style={{ height: 6, borderRadius: 6, background: "#f1e4d2", marginTop: 12 }}>
                <div style={{ width: "75%", height: "100%", borderRadius: 6, background: "var(--orange-signal)" }} />
              </div>
            </div>
            <div className="glass float-b" style={{ right: 46, top: 96, width: 190 }}>
              <small>Approvals waiting</small>
              <div style={{ fontSize: 18, fontWeight: 600 }}>3</div>
            </div>
            <div className="glass" style={{ left: 110, top: 196, width: 450, padding: 22 }}>
              <strong>Purchase orders</strong>
              {sampleOrders.map((o) => (
                <div key={o.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
                  <div><div style={{ fontWeight: 500 }}>{o.vendor}</div><small>{o.id}</small></div>
                  <span className={`badge ${o.status === "In review" ? "warn" : ""}`}>{o.status}</span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}