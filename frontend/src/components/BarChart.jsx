// A small dependency-free bar chart drawn as SVG. Values come from the API, never from this file.
export default function BarChart({ data, title, format = (v) => String(v), color = "#e8590c" }) {
  const W = 640, H = 240, L = 58, R = 12, T = 14, B = 44;
  const max = Math.max(0, ...data.map((d) => d.value));
  const top = max === 0 ? 1 : niceCeil(max);
  const slot = (W - L - R) / Math.max(data.length, 1);
  const bar = Math.min(slot * 0.62, 56);
  const y = (v) => T + (H - T - B) * (1 - v / top);

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: ${data.map((d) => `${d.label} ${format(d.value)}`).join(", ")}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <g key={f}>
            <line x1={L} x2={W - R} y1={y(top * f)} y2={y(top * f)} stroke="#e3d8c8" strokeWidth="1" />
            <text x={L - 8} y={y(top * f) + 4} textAnchor="end" fontSize="11" fill="#6b6258">{format(top * f, true)}</text>
          </g>
        ))}
        {data.map((d, i) => {
          const x = L + slot * i + (slot - bar) / 2;
          const h = Math.max(d.value > 0 ? 2 : 0, y(0) - y(d.value));
          return (
            <g key={d.label}>
              <rect x={x} y={y(0) - h} width={bar} height={h} rx="5" fill={color}><title>{`${d.label}: ${format(d.value)}`}</title></rect>
              <text x={x + bar / 2} y={H - 22} textAnchor="middle" fontSize="11" fill="#6b6258">{d.label}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="muted">{title}</figcaption>
    </figure>
  );
}

function niceCeil(v) {
  const p = 10 ** Math.floor(Math.log10(v));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}