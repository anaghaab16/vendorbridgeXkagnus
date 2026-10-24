import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

const EMPTY = { name: "", category: "", gst_number: "", contact_no: "", status: "pending" };
const FILTERS = ["all", "active", "pending", "blocked"];

export default function Vendors() {
  const { user } = useAuth();
  const canDelete = ["admin", "manager"].includes(user.role);
  const [vendors, setVendors] = useState(null);
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("all");
  const [form, setForm] = useState(null); // null = form closed
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setVendors(await api("/vendors"));
    } catch (e) {
      setError(e.message);
      setVendors([]);
    }
  }
  useEffect(() => { load(); }, []);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const count = (s) => (vendors || []).filter((v) => s === "all" || v.status === s).length;
  const shown = (vendors || []).filter(
    (v) =>
      (filter === "all" || v.status === filter) &&
      `${v.name} ${v.gst_number || ""} ${v.category || ""}`.toLowerCase().includes(q.toLowerCase())
  );

  async function save(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const { id, created_at, ...payload } = form;
    try {
      await api(id ? `/vendors/${id}` : "/vendors", { method: id ? "PUT" : "POST", body: payload });
      setForm(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(v) {
    if (!window.confirm(`Delete ${v.name}?`)) return;
    try {
      await api(`/vendors/${v.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Vendors</h1>
        <button className="btn primary" onClick={() => { setError(""); setForm({ ...EMPTY }); }}>+ Add Vendor</button>
      </div>
      <p className="lead">Manage supplier profiles and registrations</p>

      {error && <p className="error" role="alert">{error}</p>}

      {form && (
        <form className="card vendor-form" onSubmit={save}>
          <h3>{form.id ? "Vendor details" : "Add vendor"}</h3>
          <div className="form-grid">
            <label>Vendor name<input value={form.name} onChange={set("name")} required minLength={2} /></label>
            <label>Category<input value={form.category || ""} onChange={set("category")} placeholder="e.g. IT, Construction" /></label>
            <label>GST number<input value={form.gst_number || ""} onChange={set("gst_number")} placeholder="27AABCS1429B1Z5" maxLength={15} /></label>
            <label>Contact no.<input type="tel" value={form.contact_no || ""} onChange={set("contact_no")} placeholder="+91 98765 43210" /></label>
            <label>Status
              <select value={form.status} onChange={set("status")}>
                <option value="pending">Pending</option>
                <option value="active">Active</option>
                <option value="blocked">Blocked</option>
              </select>
            </label>
          </div>
          <div className="actions">
            <button type="button" onClick={() => setForm(null)}>Cancel</button>
            <button type="submit" className="btn primary" disabled={busy}>{busy ? "Saving..." : "Save vendor"}</button>
          </div>
        </form>
      )}

      <input className="search" placeholder="Search by name, GST number, category..." value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips">
        {FILTERS.map((f) => (
          <button key={f} className={`chip ${filter === f ? "on" : ""}`} onClick={() => setFilter(f)}>
            {f[0].toUpperCase() + f.slice(1)} ({count(f)})
          </button>
        ))}
      </div>

      {vendors === null ? (
        <p className="center">Loading...</p>
      ) : shown.length === 0 ? (
        <div className="card empty"><h3>No vendors found</h3><p>Click "+ Add Vendor" to create one.</p></div>
      ) : (
        <table>
          <thead><tr><th>Vendor name</th><th>Category</th><th>GST no.</th><th>Contact no.</th><th>Status</th><th>Action</th></tr></thead>
          <tbody>
            {shown.map((v) => (
              <tr key={v.id}>
                <td><strong>{v.name}</strong></td>
                <td>{v.category || "-"}</td>
                <td>{v.gst_number || "-"}</td>
                <td>{v.contact_no || "-"}</td>
                <td><span className={`pill ${v.status}`}>{v.status}</span></td>
                <td className="row-actions">
                  <button onClick={() => { setError(""); setForm({ ...v }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>View</button>
                  {canDelete && <button className="danger" onClick={() => remove(v)}>Delete</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}