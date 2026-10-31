import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { uploadFile } from "../files.js";
import { ratingLabel, todayISO } from "../format.js";

const EMPTY_ITEM = { item_name: "", quantity: "", unit: "pcs" };
const MAX_FILES = 5;
const MAX_MB = 5;

export default function RFQForm() {
  const navigate = useNavigate();
  const mode = useRef("draft"); // which button was pressed
  const [form, setForm] = useState({ title: "", category: "", deadline: "", description: "" });
  const [items, setItems] = useState([{ ...EMPTY_ITEM }]);
  const [vendors, setVendors] = useState(null);
  const [picked, setPicked] = useState([]);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/vendors")
      .then((v) => setVendors(v.filter((x) => x.status !== "blocked")))
      .catch((e) => { setError(e.message); setVendors([]); });
  }, []);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const setItem = (i, key) => (e) => setItems(items.map((it, n) => (n === i ? { ...it, [key]: e.target.value } : it)));
  const togglePick = (id) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]);

  function addFiles(e) {
    const next = [...files, ...Array.from(e.target.files)];
    e.target.value = "";
    if (next.length > MAX_FILES) return setError(`You can attach at most ${MAX_FILES} files`);
    if (next.some((f) => f.size > MAX_MB * 1024 * 1024)) return setError(`Each file must be ${MAX_MB} MB or smaller`);
    setError("");
    setFiles(next);
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    const send = mode.current === "send";
    if (send && picked.length === 0) return setError("Choose at least one vendor before sending");
    setBusy(true);
    try {
      const rfq = await api("/rfqs", {
        method: "POST",
        body: {
          ...form,
          items: items.map((i) => ({ item_name: i.item_name, quantity: Number(i.quantity), unit: i.unit })),
          vendor_ids: picked,
          send,
        },
      });
      const failed = [];
      for (const f of files) {
        try { await uploadFile(`/rfqs/${rfq.id}/attachments`, f); } catch (err) { failed.push(`${f.name} (${err.message})`); }
      }
      const notice = failed.length
        ? `RFQ saved, but some files were not uploaded: ${failed.join("; ")}`
        : send ? "RFQ sent to the selected vendors." : "RFQ saved as a draft.";
      navigate(`/rfqs/${rfq.id}`, { state: { notice } });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="page-head"><h1>Create RFQ</h1><Link className="btn" to="/rfqs">Back</Link></div>
      <p className="lead">Describe what you need, add items, choose vendors and set a deadline</p>
      {error && <p className="error" role="alert">{error}</p>}

      <section className="card form-section">
        <h3>Details</h3>
        <div className="form-grid">
          <label className="wide">RFQ title<input value={form.title} onChange={set("title")} required minLength={3} placeholder="Office furniture procurement Q2" /></label>
          <label>Category<input value={form.category} onChange={set("category")} required minLength={2} placeholder="e.g. Furniture" /></label>
          <label>Quotation deadline<input type="date" value={form.deadline} onChange={set("deadline")} required min={todayISO()} /></label>
          <label className="wide">Description<textarea rows={3} value={form.description} onChange={set("description")} maxLength={2000} placeholder="Delivery location, quality needs, anything vendors should know" /></label>
        </div>
      </section>

      <section className="card form-section">
        <h3>Items</h3>
        {items.map((it, i) => (
          <div className="item-row" key={i}>
            <input aria-label="Item name" placeholder="Item or service" value={it.item_name} onChange={setItem(i, "item_name")} required />
            <input aria-label="Quantity" type="number" min="0.01" step="any" placeholder="Qty" value={it.quantity} onChange={setItem(i, "quantity")} required />
            <input aria-label="Unit" placeholder="Unit" value={it.unit} onChange={setItem(i, "unit")} required maxLength={30} />
            <button type="button" disabled={items.length === 1} onClick={() => setItems(items.filter((_, n) => n !== i))}>Remove</button>
          </div>
        ))}
        <button type="button" onClick={() => setItems([...items, { ...EMPTY_ITEM }])} disabled={items.length >= 50}>+ Add item</button>
      </section>

      <section className="card form-section">
        <h3>Assign vendors</h3>
        {vendors === null ? <p>Loading vendors...</p> : vendors.length === 0 ? (
          <p>No vendors yet. <Link className="lk" to="/vendors">Add vendors first.</Link></p>
        ) : (
          <div className="pick-list">
            {vendors.map((v) => (
              <label key={v.id} className={`pick ${picked.includes(v.id) ? "on" : ""}`}>
                <input type="checkbox" checked={picked.includes(v.id)} onChange={() => togglePick(v.id)} />
                <span className="pick-name">{v.name}</span>
                <span className="muted">{v.category || "No category"}</span>
                <span className="rating">{ratingLabel(v.rating)}</span>
                {!v.email && <span className="muted warn" title="Without an email, no vendor user can see this RFQ">no login email</span>}
              </label>
            ))}
          </div>
        )}
      </section>

      <section className="card form-section">
        <h3>Attachments</h3>
        <input type="file" multiple onChange={addFiles} accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.xls,.xlsx,.csv,.txt" />
        <p className="muted">Up to {MAX_FILES} files, {MAX_MB} MB each (PDF, images, Word, Excel, CSV, text)</p>
        {files.map((f, i) => (
          <div className="file-row" key={i}>{f.name}<button type="button" onClick={() => setFiles(files.filter((_, n) => n !== i))}>Remove</button></div>
        ))}
      </section>

      <div className="actions">
        <button type="submit" disabled={busy} onClick={() => (mode.current = "draft")}>Save as draft</button>
        <button type="submit" className="btn primary" disabled={busy} onClick={() => (mode.current = "send")}>{busy ? "Saving..." : "Save and send to vendors"}</button>
      </div>
    </form>
  );
}