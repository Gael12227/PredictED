import type { CsvSummary } from "../lib/types";
import { fmt } from "../lib/format";

export function ContextInsights({ summary, loading }: { summary: CsvSummary | null; loading: boolean }) {
  return (
    <div className="card">
      <div className="card-title">
        <h2>Dataset insights · {summary?.context === "rural" ? "Rural (Delhi)" : "Urban (Delhi)"}</h2>
        <span className="small muted">
          {summary ? `${summary.rows.toLocaleString()} historical days` : ""}
        </span>
      </div>
      {loading && <div className="small faint">Loading context…</div>}
      {!loading && !summary && <div className="empty">Context CSV not loaded.</div>}
      {!loading && summary && (
        <>
          <div className="small muted" style={{ lineHeight: 1.6 }}>
            {summary.monthly ? (
              <>
                Month {summary.month}: <b>{summary.monthly.count} days</b> · median NEDOCS{" "}
                <b>{fmt(summary.monthly.median, 0)}</b> · p90{" "}
                <b>{fmt(summary.monthly.p90, 0)}</b>
                {summary.monthly.occ != null && (
                  <> · mean occupancy <b>{fmt(summary.monthly.occ, 0)}%</b></>
                )}
              </>
            ) : (
              "No monthly aggregation for this archetype."
            )}
            {" "}· overall mean {fmt(summary.global.mean, 0)} (p90 {fmt(summary.global.p90, 0)})
          </div>

          {summary.complaints.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div className="card-title">
                <h2>Dominant chief complaints</h2>
              </div>
              <div className="row-flex">
                {summary.complaints.map((c) => (
                  <span key={c.complaint} className="status-pill pill-plain" title={`mean NEDOCS ${c.mean_nedocs ?? "—"} on complaint days`}>
                    {c.complaint}
                    <b style={{ color: "var(--ink)" }}>{c.share_pct}%</b>
                  </span>
                ))}
              </div>
            </div>
          )}

          {summary.weather.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="card-title">
                <h2>Frequent conditions</h2>
              </div>
              <div className="row-flex">
                {summary.weather.map((w) => (
                  <span key={w.weather} className="chip" style={{ background: "var(--line-2)", color: "var(--ink-2)" }}>
                    {w.weather} · {w.days} d
                  </span>
                ))}
              </div>
            </div>
          )}

          {Object.keys(summary.aqi_bins).length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="card-title">
                <h2>NEDOCS by air-quality band</h2>
              </div>
              <div className="row-flex">
                {Object.entries(summary.aqi_bins).map(([bin, v]) => (
                  <span key={bin} className="status-pill pill-plain" title={`${v.count} days`}>
                    AQI {bin}: <b style={{ color: "var(--ink)" }}>{fmt(v.mean, 0)}</b>
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
