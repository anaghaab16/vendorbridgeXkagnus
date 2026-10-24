import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import PhotoPicker from "../components/PhotoPicker";
import { useAuth } from "../auth.jsx";

const ROLES = [
  ["procurement_officer", "Procurement officer"],
  ["manager", "Manager"],
  ["admin", "Admin"],
  ["vendor", "Vendor"],
];
const EMPTY = { first_name: "", last_name: "", email: "", phone: "", role: "procurement_officer", country: "", additional_info: "", password: "" };

export default function Register() {
  const navigate = useNavigate();
  const { register, login } = useAuth();
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(form);
      await login(form.email, form.password);
      navigate("/");
    } catch (err) {
      setError(err?.message || "Could not create account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <form className="ob-form tight" onSubmit={handleSubmit}>
        <strong style={{ fontSize: 18 }}>VendorBridge</strong>
        <h1 style={{ fontSize: 30 }}>Create your account</h1>

        {/* preview only: the backend has no photo upload yet, so the file is not sent */}
        <PhotoPicker hint="Preview only for now. Upload comes later." />

        {error && <p className="ob-error" role="alert">{error}</p>}

        <div className="ob-row">
          <div className="ob-field"><label htmlFor="fn">First name</label>
            <input id="fn" className="ob-input" value={form.first_name} onChange={set("first_name")} required /></div>
          <div className="ob-field"><label htmlFor="ln">Last name</label>
            <input id="ln" className="ob-input" value={form.last_name} onChange={set("last_name")} required /></div>
        </div>
        <div className="ob-row">
          <div className="ob-field"><label htmlFor="em">Email address</label>
            <input id="em" type="email" className="ob-input" value={form.email} onChange={set("email")} required /></div>
          <div className="ob-field"><label htmlFor="ph">Phone number</label>
            <input id="ph" type="tel" className="ob-input" placeholder="+91 98765 43210" pattern="\+?[0-9 \-]{10,16}"
              title="10 to 15 digits, spaces or dashes" value={form.phone} onChange={set("phone")} required /></div>
        </div>
        <div className="ob-row">
          <div className="ob-field"><label htmlFor="rl">Role</label>
            <select id="rl" className="ob-input" value={form.role} onChange={set("role")}>
              {ROLES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select></div>
          <div className="ob-field"><label htmlFor="co">Country</label>
            <input id="co" className="ob-input" value={form.country} onChange={set("country")} minLength={2} required /></div>
        </div>
        <div className="ob-field"><label htmlFor="ai">Additional information</label>
          <textarea id="ai" className="ob-input" maxLength={500} value={form.additional_info} onChange={set("additional_info")} /></div>
        <div className="ob-field"><label htmlFor="pw">Password</label>
          <input id="pw" type="password" minLength={8} className="ob-input" value={form.password} onChange={set("password")} required /></div>

        <button type="submit" className="ob-btn primary" disabled={busy}>{busy ? "Creating..." : "Register"}</button>
        <p>Already have an account? <Link className="ob-link" to="/login">Sign in</Link></p>
      </form>
    </AuthLayout>
  );
}