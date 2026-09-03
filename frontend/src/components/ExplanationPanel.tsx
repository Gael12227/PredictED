import type { Archetype, Factor } from "../lib/types";
import { LEVEL_STYLES, TAG_LABELS } from "../lib/types";

const SEV_CLASS: Record<string, string> = {
  info: "sev-info",
  low: "sev-low",
  medium: "sev-medium",
  high: "sev-high",
};

function FactorRow({ f }: { f: Factor }) {
  return (
    <div className="factor">
      <span className={`sev-dot ${SEV_CLASS[f.severity] ?? "sev-info"}`} />
      <span className="tag-chip">{TAG_LABELS[f.tag] ?? f.tag}</span>
      <span className="small" style={{ color: "var(--ink-2)", lineHeight: 1.5 }}>
        {f.text}
      </span>
    </div>
  );
}

export function ExplanationPanel({ archetype }: { archetype: Archetype | null }) {
  if (!archetype) return <div className="card empty">Waiting for explanation…</div>;
  const level = LEVEL_STYLES[archetype.level];
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column" }}>
      <div className="card-title">
        <h2>Why this risk level</h2>
        <span
          className="status-pill"
          style={{ color: level.color, background: level.soft, border: `1px solid ${level.color}22` }}
        >
          {archetype.level_label}
        </span>
      </div>

      <div style={{ fontSize: "0.92rem", lineHeight: 1.55, color: "var(--ink-2)" }}>
        {archetype.summary}
      </div>

      <div style={{ marginTop: 12 }}>
        {archetype.factors.length === 0 && (
          <div className="small muted">
            No factor is breaching its threshold — conditions are within normal operating range.
          </div>
        )}
        {archetype.factors.map((f, i) => (
          <FactorRow key={i} f={f} />
        ))}
      </div>

      <div className="divider" />

      <div className="card-title">
        <h2>Recommended actions</h2>
      </div>
      {archetype.actions.map((a, i) => (
        <div className="action" key={i}>
          <span className="tick">✓</span>
          <span>{a}</span>
        </div>
      ))}

      {archetype.context_note && (
        <div className="note-box" style={{ marginTop: "auto", paddingTop: 12 }}>
          {archetype.context_note}
        </div>
      )}
      {archetype.environment_note && (
        <div className="note-box env">{archetype.environment_note}</div>
      )}
    </div>
  );
}
