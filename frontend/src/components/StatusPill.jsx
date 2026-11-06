export default function StatusPill({ status }) {
  return <span className={`pill ${status}`}>{String(status).replaceAll("_", " ")}</span>;
}