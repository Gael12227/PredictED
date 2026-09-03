import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryPoint } from "../lib/types";
import { fmt } from "../lib/format";

export function TrendChart({
  history,
  hospitalType,
  months,
  currentScore,
  loading,
}: {
  history: HistoryPoint[];
  hospitalType: string;
  months: number;
  currentScore: number | null;
  loading: boolean;
}) {
  return (
    <div className="card">
      <div className="card-title">
        <h2>Historical context · {hospitalType}</h2>
        <span className="small muted">last {months} months from CSV · monthly means</span>
      </div>
      {loading && <div className="small faint">Loading history…</div>}
      {!loading && history.length === 0 && (
        <div className="empty">No historical series available for this archetype.</div>
      )}
      {!loading && history.length > 0 && (
        <>
          <ResponsiveContainer width="100%" height={230}>
            <ComposedChart data={history} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#edf1f7" />
              <XAxis
                dataKey="ym"
                tick={{ fontSize: 10, fill: "#93a1b8" }}
                interval="preserveStartEnd"
                minTickGap={28}
              />
              <YAxis
                yAxisId="nedocs"
                domain={[0, 250]}
                tick={{ fontSize: 10, fill: "#93a1b8" }}
              />
              <YAxis
                yAxisId="occ"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: "#93a1b8" }}
                unit="%"
              />
              <Tooltip
                contentStyle={{ borderRadius: 10, border: "1px solid #dfe6f0", fontSize: 12 }}
                formatter={(v, name) => [
                  fmt(v as number, 1),
                  name === "nedocs" ? "NEDOCS mean" : "Occupancy %",
                ]}
              />
              <Line
                yAxisId="nedocs"
                type="monotone"
                dataKey="nedocs"
                stroke="#0e7490"
                strokeWidth={2.2}
                dot={false}
                name="nedocs"
              />
              <Line
                yAxisId="occ"
                type="monotone"
                dataKey="occ"
                stroke="#c4a24a"
                strokeWidth={1.6}
                strokeDasharray="4 4"
                dot={false}
                name="occ"
              />
              {currentScore !== null && (
                <ReferenceLine
                  yAxisId="nedocs"
                  y={currentScore}
                  stroke="#ef4444"
                  strokeDasharray="6 3"
                  strokeWidth={1.4}
                  label={{
                    value: `now ${fmt(currentScore, 0)}`,
                    position: "insideTopRight",
                    fill: "#b91c1c",
                    fontSize: 10,
                    fontWeight: 700,
                  }}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
          <div className="legend" style={{ marginTop: 6 }}>
            <span><i className="sw" style={{ background: "#0e7490" }} /> NEDOCS score (monthly mean)</span>
            <span><i className="sw" style={{ background: "#c4a24a" }} /> Bed occupancy %</span>
            <span><i className="sw" style={{ background: "#ef4444" }} /> Current NEDOCS</span>
          </div>
        </>
      )}
    </div>
  );
}
