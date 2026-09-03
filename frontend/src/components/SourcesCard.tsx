import type { FullPayload, WebNote } from "../lib/types";
import { clock, fmt, fmtAge } from "../lib/format";

function Age({ seconds }: { seconds: number | null | undefined }) {
  return <span className="muted">{fmtAge(seconds)}</span>;
}

function WebBlock({ web }: { web?: WebNote | null }) {
  const ok = !!web?.ok;
  return (
    <div className="source-card">
      <div className="ico">🌤</div>
      <h3>Live web feed</h3>
      <p>
        {ok ? (
          <>
            Open-Meteo · Delhi. {fmt(web?.temperature_c, 1)}°C {web?.weather_text},
            AQI {fmt(web?.aqi, 0)} ({web?.aqi_category}). Updated{" "}
            {web?.fetched_at ? clock(web.fetched_at) : "—"}.
          </>
        ) : (
          <>Unavailable — {web?.error ?? "disabled"}.</>
        )}
      </p>
    </div>
  );
}

export function SourcesRow({ payload }: { payload: FullPayload | null }) {
  const s = payload?.sources;
  if (!s) {
    return (
      <div className="card">
        <div className="empty">Waiting for the live feed…</div>
      </div>
    );
  }
  const mqtt = s.mqtt;
  const web = s.web;
  return (
    <div className="source-cards">
      <div className="source-card">
        <div className="ico">📁</div>
        <h3>CSV archives</h3>
        <p>
          Delhi historical ED context loaded:{" "}
          <b>{s.csv.urban_rows.toLocaleString()}</b> urban +{" "}
          <b>{s.csv.rural_rows.toLocaleString()}</b> rural rows — baselines,
          chief complaints and monthly NEDOCS series.
        </p>
      </div>

      <WebBlock web={web} />

      {mqtt.connected ? (
        <div className="source-card">
          <div className="ico">📡</div>
          <h3>MQTT telemetry</h3>
          <p>
            Broker connected — listening on <span className="mono">predictED/state</span> +{" "}
            <span className="mono">predictED/sensor</span>. Last message:{" "}
            <Age seconds={mqtt.last_message_age_s} />.
          </p>
        </div>
      ) : s.demo.active ? (
        <div className="source-card">
          <div className="ico">🧪</div>
          <h3>Built-in simulator</h3>
          <p>
            No MQTT broker reachable, so the simulator streams EMR census +
            sensor telemetry for all four Delhi archetypes. DB rows:{" "}
            <b>{s.db.hardware_logs.toLocaleString()}</b> hardware ·{" "}
            <b>{s.db.emr_snapshots.toLocaleString()}</b> snapshots.
          </p>
        </div>
      ) : (
        <div className="source-card">
          <div className="ico">📡</div>
          <h3>MQTT telemetry</h3>
          <p>
            Broker not connected ({mqtt.error ?? "offline"}). Connect one to
            start receiving real ED streams.
          </p>
        </div>
      )}

      <div className="source-card">
        <div className="ico">⚕️</div>
        <h3>Model &amp; uptime</h3>
        <p>
          Random-forest T+2h forecast (9 features) + rule engine active.
          Backend up {fmt(s.uptime_s / 60, 0)} min · pushed every 2 s.
        </p>
      </div>
    </div>
  );
}
