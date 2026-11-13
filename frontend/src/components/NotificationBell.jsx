import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { timeAgo } from "../format.js";

export default function NotificationBell() {
  const navigate = useNavigate();
  const box = useRef(null);
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  const refreshCount = () => api("/notifications/unread-count").then((r) => setCount(r.count)).catch(() => {});

  useEffect(() => {
    refreshCount();
    const timer = setInterval(refreshCount, 30000); // new events show up within half a minute
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!open) return;
    setError("");
    api("/notifications?limit=8").then(setItems).catch((e) => { setError(e.message); setItems([]); });
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);

  async function openItem(n) {
    setOpen(false);
    if (!n.is_read) { await api(`/notifications/${n.id}/read`, { method: "POST" }).catch(() => {}); refreshCount(); }
    if (n.link) navigate(n.link);
  }

  async function readAll() {
    await api("/notifications/read-all", { method: "POST" }).catch(() => {});
    setItems((list) => (list || []).map((n) => ({ ...n, is_read: true })));
    setCount(0);
  }

  return (
    <div className="bell" ref={box}>
      <button type="button" className="bell-btn" aria-label={`Notifications, ${count} unread`} aria-expanded={open} onClick={() => setOpen(!open)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 9a6 6 0 0 1 12 0c0 6 2 7 2 7H4s2-1 2-7" /><path d="M10 20a2 2 0 0 0 4 0" />
        </svg>
        {count > 0 && <span className="bell-count">{count > 99 ? "99+" : count}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notifications">
          <div className="bell-head"><strong>Notifications</strong><button type="button" onClick={readAll} disabled={count === 0}>Mark all read</button></div>
          {error && <p className="error">{error}</p>}
          {items === null ? <p className="muted pad">Loading...</p> : items.length === 0 && !error ? (
            <p className="muted pad">You are all caught up.</p>
          ) : (
            <ul>
              {items.map((n) => (
                <li key={n.id}>
                  <button type="button" className={n.is_read ? "" : "unread"} onClick={() => openItem(n)}>
                    <span className="n-title">{n.title}</span>
                    <span className="n-msg">{n.message}</span>
                    <span className="muted">{timeAgo(n.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Link className="bell-all" to="/notifications" onClick={() => setOpen(false)}>See all notifications</Link>
        </div>
      )}
    </div>
  );
}