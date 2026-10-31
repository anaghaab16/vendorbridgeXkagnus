export default function StatusPill({ status }) {
  return <span className={`pill ${status}`}>{status}</span>;
}