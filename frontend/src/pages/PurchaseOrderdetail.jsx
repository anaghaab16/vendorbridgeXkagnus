import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import DocumentSheet from "../components/DocumentSheet.jsx";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate } from "../format.js";

export default function PurchaseOrderDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [po, setPo] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const canInvoice = ["admin", "procurement_officer"].includes(user.role);

  useEffect(() => { api(`/purchase-orders/${id}`).then(setPo).catch((e) => setError(e.message)); }, [id]);

  async function createInvoice() {
    setError(""); setBusy(true);
    try {
      const inv = await api("/invoices", { method: "POST", body: { po_id: Number(id) } });
      navigate(`/invoices/${inv.id}`);
    } catch (e) { setError(e.message); setBusy(false); }
  }

  if (!po) return error ? <p className="error" role="alert">{error}</p> : <p className="center">Loading...</p>;

  return (
    <>
      <div className="page-head no-print">
        <h1>Purchase order</h1>
        <Link className="btn" to="/purchase-orders">Back</Link>
      </div>
      {error && <p className="error no-print" role="alert">{error}</p>}
      <div className="actions no-print">
        <button onClick={() => window.print()}>Print</button>
        {po.invoice_id
          ? <Link className="btn primary" to={`/invoices/${po.invoice_id}`}>View invoice {po.invoice_number}</Link>
          : canInvoice && po.status === "issued" && <button className="btn primary" disabled={busy} onClick={createInvoice}>{busy ? "Creating..." : "Generate invoice"}</button>}
        <Link className="btn" to={`/rfqs/${po.rfq_id}`} hidden={user.role === "vendor"}>Open RFQ</Link>
      </div>
      <DocumentSheet
        title="Purchase order" number={po.po_number}
        meta={[["PO date", formatDate(po.po_date)], ["RFQ", po.rfq_number || "-"], ["Delivery", po.delivery_days ? `${po.delivery_days} days` : "-"],
               ["Payment terms", po.payment_terms || "-"], ["Status", <StatusPill key="s" status={po.status} />]]}
        buyer={po.buyer} vendor={po.vendor} items={po.items} totals={po.totals}
        footer={`Issued by ${po.created_by_name} from approved quotation of ${po.vendor.name}.`}
      />
    </>
  );
}