// File upload and download need the token and are not JSON, so they do not use api.js
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

async function failMessage(res) {
  try {
    const d = await res.json();
    if (typeof d.detail === "string") return d.detail;
    if (Array.isArray(d.detail)) return d.detail.map((x) => `${x.loc.at(-1)}: ${x.msg}`).join(". ");
  } catch { /* keep default */ }
  return "Something went wrong";
}

export async function uploadFile(path, file) {
  const body = new FormData();
  body.append("file", file);
  let res;
  try {
    res = await fetch(BASE + path, { method: "POST", headers: authHeader(), body });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  if (!res.ok) throw new Error(await failMessage(res));
  return res.json();
}

export async function downloadFile(path, name) {
  let res;
  try {
    res = await fetch(BASE + path, { headers: authHeader() });
  } catch {
    throw new Error("Cannot reach the server. Is the backend running?");
  }
  if (!res.ok) throw new Error(await failMessage(res));
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}