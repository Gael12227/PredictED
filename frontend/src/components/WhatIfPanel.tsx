import { useEffect, useRef, useState } from "react";
import type {
  Archetype,
  FeatureKey,
  WhatIfResp,
} from "../lib/types";
import { FEATURE_META, FEATURE_ORDER, LEVEL_STYLES, TAG_LABELS } from "../lib/types";
import { api } from "../lib/api";
import { clamp, fmt, fmtSigned } from "../lib/format";

type Draft = Partial<Record<FeatureKey, number>>;

const DECIMALS: Partial<Record<FeatureKey, number>> = {
  ed_pts: 0,
  ed_beds: 0,
  admits: 0,
  hosp_beds: 0,
  vents: 0,
  longest_wait: 1,
  last_wait: 1,
  arrival_velocity: 2,
  equipment_chaos_index: 1,
};

function roundTo(f: FeatureKey, v: number): number {
  const d = DECIMALS[f] ?? 0;
  const m = 10 ** d;
  return Math.round(v * m) / m;
}

function liveValue(arch: Archetype, f: FeatureKey): number {
  return arch.features[f]?.value ?? 0;
}

export function WhatIfPanel({
  archetype,
}: {
  archetype: Archetype | null;
}) {
  const [draft, setDraft] = useState<Draft>({});
  const [sim, setSim] = useState<WhatIfResp | null>(null);
  const [simFeatures, setSimFeatures] = useState<Record<string, number> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState(false);
  const archRef = useRef<Archetype | null>(null);
  archRef.current = archetype;

  // reset when switching hospital
  useEffect(() => {
    setDraft({});
    setSim(null);
    setSimFeatures(null);
    setError(null);
    setApplied(false);
  }, [archetype?.hospital_type]);

  // debounced what-if evaluation
  useEffect(() => {
    const arch = archRef.current;
    if (!arch) return;
    if (Object.keys(draft).length === 0) {
      setSim(null);
      setSimFeatures(null);
      return;
    }
    const features: Record<string, number> = {};
    for (const f of FEATURE_ORDER) {
      features[f] = draft[f] ?? liveValue(arch, f);
    }
    setBusy(true);
    const timer = setTimeout(async () => {
      try {
        const resp = await api.whatif(arch.hospital_type, features);
        setSim(resp);
        setSimFeatures(features);
        setError(null);
        setApplied(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : "What-if request failed");
      } finally {
        setBusy(false);
      }
    }, 380);
    return () => clearTimeout(timer);
  }, [draft]);

  if (!archetype) return <div className="card empty">Waiting for telemetry…</div>;

  const isDirty = Object.keys(draft).length > 0;
  const liveScore = archetype.score;
  const levelKey = archetype.level;

  const setValue = (f: FeatureKey, v: number) => {
    const next = { ...draft };
    if (Math.abs(v - liveValue(archetype, f)) < 1e-9) {
      delete next[f];
    } else {
      next[f] = roundTo(f, clamp(v, 0, 10000));
    }
    setDraft(next);
  };

  const applyScenario = (deltas: Partial<Record<FeatureKey, number>>) => {
    const next: Draft = {};
    for (const [f, delta] of Object.entries(deltas) as [FeatureKey, number][]) {
      next[f] = roundTo(f, clamp(liveValue(archetype, f) + delta, 0, 10000));
    }
    setDraft(next);
  };

  const applyToLive = async () => {
    if (!simFeatures || !archetype) return;
    try {
      await api.applyOverride(archetype.hospital_type, simFeatures);
      setDraft({});
      setSim(null);
      setSimFeatures(null);
      setApplied(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Apply failed");
    }
  };

  const resetLive = async () => {
    if (!archetype) return;
    try {
      await api.clearOverride(archetype.hospital_type);
      setDraft({});
      setSim(null);
      setSimFeatures(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed");
    }
  };

  const crossing = sim?.crossing ?? null;
  const crossingKey = crossing
    ? ((["not_busy", "busy", "overcrowded", "critical"] as const).find(
        (k) => LEVEL_STYLES[k].label === crossing.to
      ) ?? "overcrowded")
    : null;

  return (
    <div className="card">
      <div className="card-title">
        <h2>Simulation &amp; sensitivity</h2>
        <div className="right">
          {archetype.overridden && (
            <span className="status-pill pill-override">
              Override active · {archetype.override_fields.length} fields
            </span>
          )}
          <span className="small muted">
            Previews only — apply to write it into live state
          </span>
        </div>
      </div>

      <div className="scenario-row">
        <span className="small muted" style={{ fontWeight: 700 }}>
          Scenarios
        </span>
        <button className="scenario" onClick={() => setDraft({})}>
          Baseline (live)
        </button>
        <button className="scenario" onClick={() => applyScenario({ ed_pts: 15, admits: 4, arrival_velocity: 0.25 })}>
          Peak rush +15 pts
        </button>
        <button className="scenario" onClick={() => applyScenario({ arrival_velocity: 0.9, equipment_chaos_index: 3.5 })}>
          Ambulance surge
        </button>
        <button className="scenario" onClick={() => applyScenario({ admits: 6, longest_wait: 2 })}>
          Boarding wave
        </button>
        <button className="scenario" onClick={() => applyScenario({ vents: 3, equipment_chaos_index: 2 })}>
          Vent escalation
        </button>
        <button className="scenario" onClick={() => applyScenario({ ed_pts: -12, admits: -4, last_wait: -0.5 })}>
          Discharge wave
        </button>
      </div>

      <div className="divider" style={{ margin: "12px 0" }} />

      <div className="stepper-grid">
        {FEATURE_ORDER.map((f) => {
          const meta = FEATURE_META[f];
          const live = liveValue(archetype, f);
          const val = draft[f] ?? live;
          const dirty = draft[f] !== undefined;
          const sens = sim?.sensitivity.find((s) => s.feature === f);
          return (
            <div key={f} className={`stepper${dirty ? " dirty" : ""}`} title={meta.help}>
              <div className="head">
                <span className="lbl">{meta.label}</span>
                <span className="tag-chip">{TAG_LABELS[meta.tag] ?? meta.tag}</span>
              </div>
              <div className="ctrl">
                <button
                  className="nb"
                  aria-label={`decrease ${meta.label}`}
                  onClick={() => setValue(f, val - meta.step)}
                  disabled={busy}
                >
                  −
                </button>
                <input
                  type="number"
                  min={0}
                  step={meta.step}
                  value={val}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    if (!Number.isNaN(n)) setValue(f, n);
                  }}
                  aria-label={meta.label}
                />
                <button
                  className="nb"
                  aria-label={`increase ${meta.label}`}
                  onClick={() => setValue(f, val + meta.step)}
                  disabled={busy}
                >
                  +
                </button>
                <span className="small muted" style={{ marginLeft: 6 }}>
                  {meta.unit}
                </span>
              </div>
              <div className="cap">
                {sens ? (
                  <>
                    {sens.delta_now !== null && (
                      <span>
                        ±{meta.step} {meta.unit} ⇒{" "}
                        <b>{fmtSigned(sens.delta_now)} pts</b> current
                      </span>
                    )}
                    {sens.delta_2h !== null && (
                      <span>
                        ±{meta.step} {meta.unit} ⇒{" "}
                        <b>{fmtSigned(sens.delta_2h)} pts</b> T+2h forecast
                      </span>
                    )}
                  </>
                ) : (
                  <span className="faint">
                    {dirty ? "computing…" : "adjust to preview impact"}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="divider" />

      {/* summary strip */}
      <div className="whatif-strip">
        <div>
          <div className="small muted" style={{ fontWeight: 700 }}>Current</div>
          <div className="big" style={{ color: LEVEL_STYLES[levelKey].color }}>
            {fmt(liveScore, 0)}
            <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
              {" "}· {archetype.level_label}
            </span>
          </div>
        </div>
        <div style={{ fontSize: "1.2rem", color: "var(--faint)" }}>→</div>
        <div>
          <div className="small muted" style={{ fontWeight: 700 }}>Simulated</div>
          {sim ? (
            <div className="big" style={{ color: LEVEL_STYLES[sim.level].color }}>
              {fmt(sim.score, 0)}
              <span className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                {" "}· {sim.level_label}
              </span>
              <span
                style={{
                  fontSize: "0.8rem",
                  marginLeft: 10,
                  color: sim.score >= liveScore ? "var(--red)" : "var(--green)",
                  fontWeight: 700,
                }}
              >
                {fmtSigned(sim.score - liveScore, 0)}
              </span>
            </div>
          ) : (
            <div className="big faint">—</div>
          )}
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn btn-primary" onClick={applyToLive} disabled={!sim || busy || !isDirty}>
          Apply to live
        </button>
        <button className="btn btn-danger" onClick={resetLive} disabled={!archetype.overridden}>
          Reset to live feed
        </button>
      </div>

      {applied && (
        <div className="small" style={{ color: "var(--green)", marginTop: 10 }}>
          ✓ Override applied — census, trend and database updated. A new EMR
          snapshot (or Reset) will clear it.
        </div>
      )}
      {error && <div className="error-banner" style={{ marginTop: 10 }}>{error}</div>}
      {busy && !sim && <div className="small faint" style={{ marginTop: 10 }}>Evaluating…</div>}

      {crossing && crossingKey && (
        <div
          style={{
            marginTop: 12,
            padding: "10px 14px",
            borderRadius: 10,
            background: LEVEL_STYLES[crossingKey].soft,
            border: `1px solid ${LEVEL_STYLES[crossingKey].color}33`,
            color: LEVEL_STYLES[crossingKey].color,
            fontWeight: 700,
            fontSize: "0.85rem",
          }}
        >
          ⚠ Level crossing {crossing.direction === "up" ? "▲" : "▼"} — this
          scenario moves the department from <b>{crossing.from}</b> to{" "}
          <b>{crossing.to}</b> ({fmt(sim?.score ?? 0, 0)} pts).
        </div>
      )}

      {/* sensitivity table */}
      {sim && sim.sensitivity.length > 0 && (
        <>
          <div style={{ marginTop: 16, fontWeight: 700, fontSize: "0.78rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--muted)" }}>
            How each input moves the score
          </div>
          <div style={{ marginTop: 8 }}>
            {sim.sensitivity.map((s) => {
              return (
                <div className="sens-row" key={s.feature}>
                  <span className="f">
                    {s.label}{" "}
                    <span className="tag-chip">{TAG_LABELS[s.tag] ?? s.tag}</span>
                  </span>
                  <span className="m">
                    current: {s.delta_now !== null ? `${fmtSigned(s.delta_now)} pts / ${s.step} ${s.unit}` : "n/a (forecast only)"}
                  </span>
                  <span className="m">
                    T+2h: {s.delta_2h !== null ? `${fmtSigned(s.delta_2h)} pts / step` : "n/a"}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
