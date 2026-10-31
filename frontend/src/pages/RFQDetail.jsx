import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { downloadFile, uploadFile } from "../files.js";
import StatusPill from "../components/StatusPill.jsx";
import { formatDate, ratingLabel } from "../format.js";

export default function RFQDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const canManage = ["admin", "procurement_officer"].includes(user.role);
  const location = useLocation();
  const navigate = useNavigate();
  const [rfq, setRfq] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(location.state?.notice || "");

  const load = () => api(`/rfqs/${id}`).then(setRfq).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [id]);

  async function changeStatus(status, confirmText) {
    if (confirmText && !window.confirm(confirmText)) return;
    setError(""); setNotice("");
    try {
      setRfq(await api(`/rfqs/${id}/status`, { method: "PATCH", body: { status } }));
      setNotice(`RFQ is now ${status}.`);
    } catch (e) { setError(e.message); }
  }

  async function remove() {
    if (!window.confirm("Delete this draft RFQ?")) return;
    try {
      await api(`/rfqs/${id}`, { method: "DELETE" });
      navigate("/rfqs");
    } catch (e) { setError(e.message); }
  }

  async function addFile(e) {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    setError(""); setNotice("");
    try {
      await uploadFile(`/rfqs/${id}/attachments`, file);
      await load();
    } catch (err) { setError(err.message); }
  }

  const download = (a) => downloadFile(`/rfqs/${id}/attachments/${a.id}`, a.file_name).catch((e) => setError(e.message));

  if (!rfq) return error ? <p className="error" role="alert">{error}</p> : <p className="center">Loading...</p>;
  const open = rfq.status === "draft" || rfq.status === "sent";

  return (
    <>
      <div className="page-head">
        <h1>{rfq.title}</h1>
        <Link className="btn" to="/rfqs">Back</Link>
      </div>
      <p className="lead"><strong>{rfq.rfq_number}</strong> &middot; {rfq.category} &middot; deadline {formatDate(rfq.deadline)} &middot; <StatusPill status={rfq.status} />
        {rfq.status === "sent" && rfq.deadline_passed && <span className="muted warn"> deadline passed</span>}</p>
      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}

      <div className="actions">
        {canManage && rfq.status === "draft" && <button className="btn primary" onClick={() => changeStatus("sent")}>Send to vendors</button>}
        {rfq.status !== "draft" && rfq.status !== "cancelled" && <Link className="btn primary" to={`/rfqs/${id}/compare`}>Compare quotations ({rfq.quote_count})</Link>}
        {canManage && rfq.status === "sent" && <button onClick={() => changeStatus("closed", "Close this RFQ? Vendors will no longer be able to change quotations.")}>Close RFQ</button>}
        {canManage && open && <button className="danger" onClick={() => changeStatus("cancelled", "Cancel this RFQ?")}>Cancel RFQ</button>}
        {canManage && rfq.status === "draft" && <button className="danger" onClick={remove}>Delete draft</button>}
      </div>

      {rfq.selected_vendor_name && <p className="notice" role="status">Selected quotation: {rfq.selected_vendor_name}. It is ready for the approval step.</p>}

      {rfq.description && <section className="card form-section"><h3>Description</h3><p>{rfq.description}</p></section>}

      <section className="card form-section">
        <h3>Items</h3>
        <table><thead><tr><th>Item</th><th>Quantity</th><th>Unit</th></tr></thead>
          <tbody>{rfq.items.map((i) => <tr key={i.id}><td>{i.item_name}</td><td>{i.quantity}</td><td>{i.unit}</td></tr>)}</tbody></table>
      </section>

      <section className="card form-section">
        <h3>Assigned vendors</h3>
        {rfq.vendors.length === 0 ? <p>No vendors assigned.</p> : (
          <table><thead><tr><th>Vendor</th><th>Rating</th><th>Login email</th><th>Quotation</th></tr></thead>
            <tbody>{rfq.vendors.map((v) => (
              <tr key={v.vendor_id}>
                <td><strong>{v.name}</strong></td>
                <td>{ratingLabel(v.rating)}</td>
                <td>{v.email || <span className="muted warn">none, vendor cannot see this RFQ</span>}</td>
                <td>{v.quotation_status ? <span className={`pill ${v.quotation_status}`}>{v.quotation_status}</span> : <span className="muted">not quoted yet</span>}</td>
              </tr>))}
            </tbody></table>
        )}
      </section>

      <section className="card form-section">
        <h3>Attachments</h3>
        {rfq.attachments.length === 0 && <p className="muted">No files attached.</p>}
        {rfq.attachments.map((a) => (
          <div className="file-row" key={a.id}>{a.file_name} <span className="muted">({Math.max(1, Math.round(a.size / 1024))} KB)</span>
            <button type="button" onClick={() => download(a)}>Download</button></div>
        ))}
        {canManage && open && rfq.attachments.length < 5 && <input type="file" onChange={addFile} />}
      </section>
    </>
  );
}