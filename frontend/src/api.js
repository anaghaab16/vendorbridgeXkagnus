const BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export async function api(path, { method = "GET", body } = {}) {
  const token = localStorage.getItem("token");
  const url = path.startsWith("/") ? `${BASE}${path}` : `${BASE}/${path}`;
  
  const res = await fetch(url, {
    method,
    headers: { 
      "Content-Type": "application/json", 
      ...(token && { Authorization: `Bearer ${token}` }) 
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong");
  return data;
}