import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { UserIcon } from "../components/PhotoPicker";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(form.email.trim(), form.password);
      navigate("/");
    } catch (err) {
      setError(err?.message || "Wrong email or password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <form className="ob-form" onSubmit={handleSubmit}>
        <strong style={{ fontSize: 18 }}>VendorBridge</strong>
        <div className="ob-photo static">
          <span className="ob-photo-btn" aria-hidden="true"><UserIcon /></span>
        </div>
        <h1><span className="mask"><span>Welcome back</span></span></h1>
        <p>Sign in to manage your vendors and purchase orders.</p>

        {error && <p className="ob-error" role="alert">{error}</p>}

        <div className="ob-field">
          <label htmlFor="email">Username</label>
          <input id="email" type="email" className="ob-input" placeholder="Your email address" autoComplete="username" value={form.email} onChange={set("email")} required />
        </div>
        <div className="ob-field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" className="ob-input" value={form.password} onChange={set("password")} required />
        </div>

        <button type="submit" className="ob-btn primary" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
        <p><Link className="ob-link" to="/forgot-password">Forgot password?</Link></p>
        <p>New to VendorBridge? <Link className="ob-link" to="/register">Create an account</Link></p>
      </form>
    </AuthLayout>
  );
}