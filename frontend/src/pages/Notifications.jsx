import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { dateTime, timeAgo } from "../format.js";

export default function Notifications() {
  const navigate = useNavigate();
  const [items, setItems] = useState(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [error, setError] = useState("");

  const load = () => api(`/notifications?limit=100${unreadOnly ? "&unread_only=true" : ""}`).then(setItems).catch((e) => { setError(e.message); setItems([]); });
  useEffect(() => { load(); }, [unreadOnly]);

  async function open(n) {
    if (!n.is_read) await api(`/notifications/${n.id}/read`, { method: "POST" }).catch(() => {});
    if (n.link) navigate(n.link); else load();
  }
  async function readAll() { await api("/notifications/read-all", { method: "POST" }).catch((e) => setError(e.message)); load(); }

  return (
    <>
      <div className="page-head"><h1>Notifications</h1><button onClick={readAll}>Mark all as read</button></div>
      <p className="lead">Updates about RFQs, approvals, purchase orders and invoices that involve you</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="chips">
        <button className={`chip ${!unreadOnly ? "on" : ""}`} onClick={() => setUnreadOnly(false)}>All</button>
        <button className={`chip ${unreadOnly ? "on" : ""}`} onClick={() => setUnreadOnly(true)}>Unread</button>
      </div>
      {items === null ? <p className="center">Loading...</p> : items.length === 0 ? (
        <div className="card empty"><h3>{unreadOnly ? "Nothing unread" : "No notifications yet"}</h3><p>They appear here when something happens on a record that involves you.</p></div>
      ) : (
        <ul className="feed">
          {items.map((n) => (
            <li key={n.id}>
              <button type="button" className={n.is_read ? "" : "unread"} onClick={() => open(n)}>
                <strong>{n.title}</strong>
                <span>{n.message}</span>
                <span className="muted" title={dateTime(n.created_at)}>{timeAgo(n.created_at)} &middot; {n.is_read ? "read" : "unread"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}