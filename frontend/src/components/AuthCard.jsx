export default function AuthCard({ title, error, children }) {
  return (
    <div className="auth-wrap">
      <div className="card auth-card">
        <h1>{title}</h1>
        {error && <p className="error">{error}</p>}
        {children}
      </div>
    </div>
  );
}
