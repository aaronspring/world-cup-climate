import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Match, VarMeta } from "./types";

const fmtTick = (iso: string) => {
  const d = new Date(iso);
  return d.getUTCHours() === 0
    ? d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })
    : `${String(d.getUTCHours()).padStart(2, "0")}h`;
};

export default function Chart({
  match,
  varKey,
  meta,
}: {
  match: Match;
  varKey: string;
  meta: VarMeta;
}) {
  const { time, venue, team_a, team_b } = match.series;
  const data = time.map((t, i) => ({
    t,
    venue: venue[varKey][i],
    a: team_a[varKey][i],
    b: team_b[varKey][i],
  }));
  const kickoff = match.kickoff_utc;

  return (
    <ResponsiveContainer width="100%" height={210}>
      <ComposedChart data={data} margin={{ top: 8, right: 6, bottom: 0, left: -18 }}>
        <defs>
          <linearGradient id="venueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={meta.color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={meta.color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="t"
          tickFormatter={fmtTick}
          minTickGap={36}
          tick={{ fill: "#7c869a", fontSize: 10 }}
          axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
          tickLine={false}
        />
        <YAxis
          width={44}
          tick={{ fill: "#7c869a", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          unit={meta.unit.length <= 2 ? meta.unit : ""}
        />
        <Tooltip
          contentStyle={{
            background: "rgba(16,22,34,0.95)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 12,
            fontSize: 12,
          }}
          labelFormatter={(t) =>
            new Date(t as string).toLocaleString("en-US", {
              month: "short", day: "numeric", hour: "2-digit", timeZone: "UTC",
            }) + " UTC"
          }
          formatter={(v: number, name) => [`${v}${meta.unit}`, name]}
        />
        <ReferenceLine
          x={kickoff}
          stroke="#facc15"
          strokeDasharray="4 3"
          label={{ value: "kickoff", fill: "#facc15", fontSize: 10, position: "insideTopRight" }}
        />
        <Area type="monotone" dataKey="venue" stroke="none" fill="url(#venueFill)" name="Venue" />
        <Line type="monotone" dataKey="venue" name="Venue" stroke={meta.color} strokeWidth={2.4} dot={false} />
        <Line type="monotone" dataKey="a" name={match.stats.team_a.home} stroke="#38bdf8" strokeWidth={1.6} strokeDasharray="5 3" dot={false} />
        <Line type="monotone" dataKey="b" name={match.stats.team_b.home} stroke="#c084fc" strokeWidth={1.6} strokeDasharray="5 3" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
