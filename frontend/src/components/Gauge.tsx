import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  YAxis,
} from "recharts";
import type { Archetype, LevelKey } from "../lib/types";
import { LEVEL_STYLES } from "../lib/types";
import { clamp, fmt, fmtAge, fmtPct, levelIndex } from "../lib/format";

const SEGMENTS: { key: LevelKey; width: number }[] = [
  { key: "not_busy", width: 60 },
  { key: "busy", width: 40 },
  { key: "overcrowded", width: 40 },
  { key: "critical", width: 110 },
];
const MAX = 250;

function QuickTile({ k, v, unit }: { k: string; v: string | number; unit?: string }) {
  return (
    <div className="tile">
      <div className="k">{k}</div>
      <div className="v">
        {v}
        {unit && <small> {unit}</small>}
      </div>
    </div>
  );
}

export function GaugeCard({ archetype }: { archetype: Archetype | null }) {
  if (!archetype) return <div className="card empty">Waiting for live telemetry…</div>;
  const score = archetype.score;
  const level = LEVEL_STYLES[archetype.level as LevelKey];
  const forecast = archetype.forecast;
  const fLevel = LEVEL_STYLES[forecast.level];
  const pct = clamp(score / MAX, 0, 1) * 100;

  const feats = archetype.features;
  const edPts = feats.ed_pts?.value ?? 0;
  const edBeds = feats.ed_beds?.value ?? 1;
  const admits = feats.admits?.value ?? 0;
  const util = edBeds > 0 ? (edPts / edBeds) * 100 : 0;
  const admitBlock = edBeds > 0 ? (admits / edBeds) * 100 : 0;
  const hw = archetype.hardware;
  const trend = archetype.trend_tail.map((p) => ({ v: p.now }));

  return (
    <div className="card">
      <div className="card-title">
        <h2>Current overcrowding risk</h2>
        <span className={`status-pill ${level.soft ? "pill-plain" : ""}`} style={{
          color: level.color, background: level.soft, border: `1px solid ${level.color}22`,
        }}>
          {level.label}
        </span>
      </div>

      <div className="gauge-wrap">
        <div className="gauge-number" style={{ color: level.color }}>{fmt(score, 0)}</div>
        <div className="gauge-sub">
          NEDOCS score · {fmtAge(archetype.last_census_age_s)} census ·{" "}
          {archetype.mode === "override" ? "override applied" : archetype.mode}
        </div>

        <div className="level-bar">
          <div className="segments">
            {SEGMENTS.map((s) => (
              <div
                key={s.key}
                style={{
                  width: `${(s.width / MAX) * 100}%`,
                  background: LEVEL_STYLES[s.key].bar,
                  opacity: levelIndex(s.key) > levelIndex(archetype.level) ? 0.28 : 0.95,
                }}
              />
            ))}
          </div>
          <div className="marker" style={{ left: `${pct}%` }}>
            <div className="needle" />
          </div>
          <div className="ticks">
            <span>0</span>
            <span>60</span>
            <span>100</span>
            <span>140</span>
            <span>250</span>
          </div>
        </div>

        <div className="row-flex" style={{ width: "100%", justifyContent: "space-between" }}>
          <div>
            <div className="small muted" style={{ fontWeight: 600 }}>T+2h forecast</div>
            <div style={{ fontSize: "1.3rem", fontWeight: 800, color: fLevel.color }}>
              {fmt(forecast.score_2h, 0)}
              <span style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600 }}>
                {" "}· {forecast.level_label}
              </span>
            </div>
          </div>
          {trend.length > 1 && (
            <div style={{ width: 150, height: 52 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={level.color} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={level.color} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <YAxis hide domain={["dataMin - 8", "dataMax + 8"]} />
                  <Tooltip
                    contentStyle={{ fontSize: 12 }}
                    formatter={(v) => [fmt(v as number, 0), "NEDOCS"]}
                  />
                  <Area type="monotone" dataKey="v" stroke={level.color} strokeWidth={2} fill="url(#spark)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      <div className="tiles">
        <QuickTile k="ED utilization" v={fmtPct(util)} />
        <QuickTile k="Admits block ED beds" v={fmtPct(admitBlock)} />
        <QuickTile k="Longest wait" v={fmt(feats.longest_wait?.value, 1)} unit="h" />
        <QuickTile
          k="Arrival velocity"
          v={fmt(hw.arrival_velocity?.value ?? 0, 2)}
          unit="pts/min"
        />
        <QuickTile k="Movement chaos" v={fmt(hw.equipment_chaos_index?.value ?? 0, 1)} unit="/10" />
        <QuickTile k="Ambient noise" v={fmt(hw.ambient_noise_db?.value ?? 0, 0)} unit="dB" />
      </div>
      <div className="legend" style={{ marginTop: 10 }}>
        <span><i className="sw" style={{ background: level.soft, border: `1px solid ${level.color}` }} /> current band: {archetype.level_label}</span>
        <span className="faint">T+2h forecast band: {archetype.forecast.level_label}</span>
      </div>
    </div>
  );
}
