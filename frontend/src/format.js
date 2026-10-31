const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
export const money = (n) => (n == null ? "-" : inr.format(n));

export function formatDate(iso) {
  if (!iso) return "-";
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export const ratingLabel = (r) => (r > 0 ? `\u2605 ${Number(r).toFixed(1)}` : "Not rated");

// today in the user's own time zone, as YYYY-MM-DD (for date input limits)
export const todayISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);