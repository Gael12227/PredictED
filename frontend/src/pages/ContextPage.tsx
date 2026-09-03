import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useSocket } from "../lib/ws";
import type { ContextKey, CsvSummary, HistoryPoint } from "../lib/types";
import { LEVEL_STYLES } from "../lib/types";
import { api } from "../lib/api";
import { fmt, fmtPct, clock } from "../lib/format";
import { GaugeCard } from "../components/Gauge";
import { ExplanationPanel } from "../components/ExplanationPanel";
import { WhatIfPanel } from "../components/WhatIfPanel";
import { DriverCard } from "../components/DriverCard";
import { TrendChart } from "../components/TrendChart";
import { ContextInsights } from "../components/ContextInsights";
import { SourcesRow } from "../components/SourcesCard";

const CONTEXT_META: Record<ContextKey, { title: string; blurb: string }> = {
  urban: {
    title: "Urban (Delhi)",
    blurb: "Big & small urban hospitals · tourist-season profile · Delhi_urban.csv",
  },
  rural: {
    title: "Rural (Delhi outskirts)",
    blurb: "Big & small rural hospitals · agricultural-season profile · delhi_Rural.csv",
  },
};

export function ContextPage({ context }: { context: ContextKey }) {
  const { payload } = useSocket();
  const ctx = payload?.contexts[context];
  const meta = CONTEXT_META[context];

  const [archId, setArchId] = useState<string | null>(null);
  const [summary, setSummary] = useState<CsvSummary | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loadingCsv, setLoadingCsv] = useState(true);
  const [csvError, setCsvError] = useState<string | null>(null);

  const archetypes = ctx?.archetypes ?? [];
  const active = useMemo(
    () => archetypes.find((a) => a.id === (archId ?? archetypes[0]?.id)) ?? archetypes[0] ?? null,
    [archetypes, archId]
  );

  useEffect(() => {
    if (archetypes.length && !archetypes.some((a) => a.id === archId)) {
      setArchId(archetypes[0].id);
    }
  }, [archetypes, archId]);

  const hospitalType = active?.hospital_type;

  useEffect(() => {
    if (!hospitalType) return;
    let cancelled = false;
    setLoadingCsv(true);
    setCsvError(null);
    Promise.all([api.summary(context, hospitalType), api.history(context, hospitalType, 60)])
      .then(([sum, hist]) => {
        if (cancelled) return;
        setSummary(sum);
        setHistory(hist.points);
      })
      .catch((e) => {
        if (!cancelled) setCsvError(e instanceof Error ? e.message : "CSV load failed");
      })
      .finally(() => {
        if (!cancelled) setLoadingCsv(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hospitalType, context]);

  const levelStyle = active ? LEVEL_STYLES[active.level] : null;
  const util =
    active && (active.features.ed_beds?.value ?? 0) > 0
      ? ((active.features.ed_pts?.value ?? 0) / (active.features.ed_beds?.value ?? 1)) * 100
      : null;

  return (
    <div className="page">
      <div className="context-head">
        <div>
          <h1>{meta.title}</h1>
          <div className="sub">{meta.blurb}</div>
        </div>

        {archetypes.length > 1 && (
          <div className="pill-group">
            {archetypes.map((a) => (
              <button
                key={a.id}
                className={a.id === active?.id ? "active" : ""}
                onClick={() => setArchId(a.id)}
              >
                {a.hospital_type.replace(" (Delhi)", "").replace(" (Delhi Outskirts)", "")}
              </button>
            ))}
          </div>
        )}

        <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {active?.overridden && <span className="status-pill pill-override">Override active</span>}
          {active && !active.overridden && active.mode === "live" && (
            <span className="status-pill pill-mqtt">
              <span className="dot pulse" /> live EMR stream
            </span>
          )}
          {active && !active.overridden && active.mode !== "live" && (
            <span className="status-pill pill-warn">{active.mode} defaults</span>
          )}
          {levelStyle && (
            <span
              className="status-pill"
              style={{ color: levelStyle.color, background: levelStyle.soft }}
            >
              {fmt(active?.score ?? 0, 0)} pts · {active?.level_label}
            </span>
          )}
          <span className="small muted mono">
            {payload ? `updated ${clock(payload.generated_at)}` : ""}
          </span>
        </div>
      </div>

      {csvError && <div className="error-banner" style={{ marginBottom: 14 }}>{csvError}</div>}

      <div className="grid cols-12">
        <div style={{ gridColumn: "span 4" }} className="grid">
          <GaugeCard archetype={active} />
          {util !== null && (
            <div className="card" style={{ padding: "12px 22px" }}>
              <div className="row-flex" style={{ justifyContent: "space-between", fontSize: "0.82rem" }}>
                <span className="muted">ED utilisation</span>
                <b>{fmtPct(util)}</b>
                <span className="muted">Typical month median NEDOCS</span>
                <b>{fmt(summary?.monthly?.median ?? null, 0)}</b>
                <span className="muted">90th pct</span>
                <b>{fmt(summary?.monthly?.p90 ?? null, 0)}</b>
              </div>
            </div>
          )}
        </div>

        <div style={{ gridColumn: "span 8" }}>
          <ExplanationPanel archetype={active} />
        </div>

        <div style={{ gridColumn: "span 12" }}>
          <WhatIfPanel archetype={active} />
        </div>

        <div style={{ gridColumn: "span 5" }}>
          <DriverCard archetype={active} />
        </div>

        <div style={{ gridColumn: "span 7" }}>
          <TrendChart
            history={history}
            hospitalType={hospitalType ?? context}
            months={60}
            currentScore={active?.score ?? null}
            loading={loadingCsv}
          />
        </div>

        <div style={{ gridColumn: "span 5" }}>
          <ContextInsights summary={summary} loading={loadingCsv} />
        </div>

        <div style={{ gridColumn: "span 7" }}>
          <div className="card" style={{ height: "100%" }}>
            <div className="card-title">
              <h2>How to read this page</h2>
            </div>
            <div className="small" style={{ color: "var(--ink-2)", lineHeight: 1.7 }}>
              <b>Gauge</b> — current NEDOCS with PredictED bands (&lt;60 · 60–100 · 100–140 ·
              ≥140) plus the <b>T+2h forecast</b> from the random-forest model and a recent
              sparkline. <b>Why this risk level</b> lists the exact factors — NEDOCS term
              contributions, boarding/waits, hardware movement, air quality.{" "}
              <b>Simulation &amp; sensitivity</b> steps the nine model inputs (±buttons, no
              sliders): every change reports its precise effect on the current score and the
              T+2h forecast, flags level crossings, and can be <b>applied</b> as an override or{" "}
              <b>reset</b> back to the EMR feed. The trend chart overlays today's score on{" "}
              {hospitalType ?? "this hospital"}'s historical monthly series from the CSV.
            </div>
            <div className="row-flex" style={{ marginTop: 14 }}>
              <Link to={context === "urban" ? "/rural" : "/urban"} className="btn">
                View {context === "urban" ? "rural" : "urban"} context →
              </Link>
            </div>
          </div>
        </div>

        <div style={{ gridColumn: "span 12" }}>
          <SourcesRow payload={payload} />
        </div>
      </div>
    </div>
  );
}
