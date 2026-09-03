import type { Archetype } from "../lib/types";
import { TAG_LABELS } from "../lib/types";
import { fmt, fmtSigned } from "../lib/format";

function barColor(strength: number): string {
  const a = Math.abs(strength);
  if (a < 6) return "#94a3b8";
  if (a < 12) return "#f59e0b";
  if (a < 20) return "#f97316";
  return "#ef4444";
}

export function DriverCard({ archetype }: { archetype: Archetype | null }) {
  if (!archetype) return <div className="card empty">Waiting…</div>;
  const maxDriver = Math.max(
    1,
    ...archetype.drivers.map((d) => Math.abs(d.strength))
  );
  const terms = [...archetype.terms].sort((a, b) => b.points - a.points);
  const maxTerm = Math.max(1, ...terms.map((t) => t.points));
  const scale = Math.max(1, archetype.score + 20);

  return (
    <div className="card">
      <div className="card-title">
        <h2>Forecast drivers · T+2h</h2>
        <span className="small muted">
          model importance × deviation from typical
        </span>
      </div>
      {archetype.drivers.length === 0 ? (
        <div className="small faint">No dominant drivers right now.</div>
      ) : (
        archetype.drivers.map((d) => {
          const color = barColor(d.strength);
          const width = Math.min(100, (Math.abs(d.strength) / maxDriver) * 100);
          return (
            <div className="bar-row" key={d.feature}>
              <span className="lbl" title={d.label}>
                {d.label}
                <span style={{ marginLeft: 6 }} className="tag-chip">
                  {TAG_LABELS[d.tag] ?? d.tag}
                </span>
              </span>
              <span className="bar-track">
                <span
                  className="bar-fill"
                  style={{
                    width: `${width}%`,
                    background: color,
                    display: "block",
                    opacity: d.strength < 0 ? 0.5 : 1,
                  }}
                />
              </span>
              <span className="bar-val">{fmtSigned(d.strength, 0)}</span>
            </div>
          );
        })
      )}

      <div className="divider" />

      <div className="card-title">
        <h2>Current score anatomy</h2>
        <span className="small muted">exact NEDOCS term points</span>
      </div>
      {terms.map((t) => (
        <div className="term-row" key={t.key}>
          <span className="small" style={{ color: "var(--ink-2)" }}>{t.label}</span>
          <span className="bar-track">
            <span
              className="bar-fill"
              style={{
                width: `${Math.min(100, (t.points / maxTerm) * 100)}%`,
                background: "#0e7490",
                display: "block",
              }}
            />
          </span>
          <span className="bar-val">
            {fmt(t.points, 0)}
            <span className="faint"> ({fmt((t.points / scale) * 100, 0)}%)</span>
          </span>
        </div>
      ))}
    </div>
  );
}
