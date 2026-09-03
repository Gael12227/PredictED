import { Link } from "react-router-dom";
import { useSocket } from "../lib/ws";
import type { ContextKey } from "../lib/types";
import { LEVEL_STYLES } from "../lib/types";
import { fmt, fmtPct } from "../lib/format";
import { SourcesRow } from "../components/SourcesCard";

const CONTEXT_META: Record<ContextKey, { title: string; sub: string }> = {
  urban: {
    title: "Urban (Delhi)",
    sub: "Big & small urban hospitals · tourist-season profile",
  },
  rural: {
    title: "Rural (Delhi outskirts)",
    sub: "Big & small rural hospitals · agricultural-season profile",
  },
};

export function HomePage() {
  const { payload, connected } = useSocket();

  return (
    <div className="page">
      <section className="hero">
        <h1>Emergency Department overcrowding — explained, live.</h1>
        <p>
          PredictED fuses <b>historical ED archives (CSV)</b>, a <b>live public web feed</b>{" "}
          (Delhi weather + air quality) and <b>hardware telemetry</b> (MQTT edge sensors and
          EMR census) into one dashboard. Every score comes with a plain-language{" "}
          <b>why</b> — exact contributing terms, threshold flags, forecast drivers and
          recommended actions — plus a <b>simulation</b> view that shows precisely how each
          change moves the current NEDOCS and the T+2h forecast.
        </p>
      </section>

      {!connected && (
        <div className="error-banner" style={{ margin: "12px 0" }}>
          Backend feed not connected — is <span className="mono">uvicorn backend.main:app</span> running on port 8000?
        </div>
      )}

      <div className="source-cards">
        <div className="source-card">
          <div className="ico">📁</div>
          <h3>CSV archives</h3>
          <p>
            Delhi urban &amp; rural ED history — NEDOCS, occupancy, AQI, weather, chief
            complaints — powers baselines, seasonal context and the monthly trend chart.
          </p>
        </div>
        <div className="source-card">
          <div className="ico">🌐</div>
          <h3>Public REST API</h3>
          <p>
            Live Delhi conditions from Open-Meteo (keyless): temperature, weather and air
            quality, refreshed every 5 minutes and folded into the explanation.
          </p>
        </div>
        <div className="source-card">
          <div className="ico">📡</div>
          <h3>MQTT telemetry</h3>
          <p>
            Ultrasound-inflow, IMU and mic sensors plus EMR census snapshots over MQTT —
            arrival velocity, movement chaos and noise feed the T+2h forecast.
          </p>
        </div>
        <div className="source-card">
          <div className="ico">🧠</div>
          <h3>Model + rules</h3>
          <p>
            A trained random forest forecasts NEDOCS two hours ahead; a deterministic rule
            engine explains every score with source-tagged reasons and actions.
          </p>
        </div>
      </div>

      <div style={{ margin: "18px 0 8px" }}>
        <h2 style={{ letterSpacing: "-0.02em" }}>Open a context</h2>
        <div className="muted small">Metrics, baselines and explanations differ per dataset.</div>
      </div>

      <div className="context-tiles">
        {(["urban", "rural"] as ContextKey[]).map((ctxKey) => {
          const ctx = payload?.contexts[ctxKey];
          const archs = ctx?.archetypes ?? [];
          const meta = CONTEXT_META[ctxKey];
          const headline = archs[0];
          const level = headline ? LEVEL_STYLES[headline.level] : null;
          return (
            <Link key={ctxKey} to={`/${ctxKey}`} className="context-tile">
              <h3>{meta.title}</h3>
              <div className="sub">{meta.sub}</div>
              {headline && level ? (
                <>
                  <div className="stat">
                    <span className="muted">Current NEDOCS</span>
                    <b style={{ color: level.color }}>
                      {fmt(headline.score, 0)} · {headline.level_label}
                    </b>
                  </div>
                  <div className="stat">
                    <span className="muted">T+2h forecast</span>
                    <b>{fmt(headline.forecast.score_2h, 0)} pts</b>
                  </div>
                  <div className="stat">
                    <span className="muted">ED utilisation</span>
                    <b>
                      {fmtPct(
                        ((headline.features.ed_pts?.value ?? 0) /
                          (headline.features.ed_beds?.value ?? 1)) *
                          100
                      )}
                    </b>
                  </div>
                  {archs.length > 1 && (
                    <div className="small muted" style={{ marginTop: 8 }}>
                      {archs
                        .map((a) => `${a.hospital_type.replace(" (Delhi)", "").replace(" (Delhi Outskirts)", "")}: ${fmt(a.score, 0)}`)
                        .join(" · ")}
                    </div>
                  )}
                </>
              ) : (
                <div className="small faint" style={{ marginTop: 14 }}>Waiting for telemetry…</div>
              )}
              <div className="cta-row">
                <span className="btn btn-primary" style={{ pointerEvents: "none" }}>
                  Open dashboard →
                </span>
              </div>
            </Link>
          );
        })}
      </div>

      <div style={{ margin: "22px 0 0" }}>
        <SourcesRow payload={payload} />
      </div>

      <div className="note-box" style={{ marginTop: 18 }}>
        <b>Demo / simulation scope.</b> This project runs on simulated ED data, contains no
        patient information, and is intended for evaluation only — it must not drive real
        clinical decisions without validation. Existing Streamlit prototypes (
        <span className="mono">app.py</span>, <span className="mono">Upgraded_App.py</span>)
        remain available alongside this dashboard.
      </div>
    </div>
  );
}
