import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import AuthCard from "../components/AuthCard.jsx";

export default function Forgot() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    try { await api("/auth/forgot-password", { method: "POST", body: { email } }); setSent(true); }
    catch (err) { setError(err.message); }
  }

  return (
    <AuthCard title="Reset password" error={error}>
      {sent ? <p>If this email exists, a reset link has been sent.</p> : (
        <form onSubmit={submit}>
          <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <button className="btn" type="submit">Send reset link</button>
        </form>
      )}
      <p className="links"><Link to="/login">Back to sign in</Link></p>
    </AuthCard>
  );
}
