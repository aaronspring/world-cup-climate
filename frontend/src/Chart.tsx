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

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

// Category thresholds per variable — y value (in the variable's unit) and the
// short label drawn at the right edge. Wording matches the tooltips in MatchCard.
const THRESHOLDS: Record<string, { y: number; label: string }[]> = {
  humidex:    [{ y: 30, label: "discomfort" }, { y: 40, label: "dangerous" }, { y: 45, label: "stop exercise" }],
  utci:       [{ y: 26, label: "moderate heat" }, { y: 32, label: "strong heat" }, { y: 38, label: "very strong" }],
  wbgt:       [{ y: 28, label: "breaks possible" }, { y: 32, label: "breaks mandatory" }],
  wind_speed: [{ y: 5,  label: "breeze" }, { y: 10, label: "windy" }, { y: 15, label: "strong" }],
  d2m:        [{ y: 20, label: "muggy" }, { y: 25, label: "tropical" }],
};

export default function Chart({
  match,
  varKey,
  meta,
  forecastStart,
}: {
  match: Match;
  varKey: string;
  meta: VarMeta;
  forecastStart: string | null;
}) {
  const { time, venue, team_a, team_b } = match.series;
  const data = time.map((t, i) => ({
    t,
    venue: venue[varKey][i],
    a: team_a[varKey][i],
    b: team_b[varKey][i],
  }));
  const kickoff = match.kickoff_utc;
  // one tick per UTC midnight so the axis reads as dates, not repeated hours
  const dayTicks = time.filter((t) => new Date(t).getUTCHours() === 0);
  // snap the cycle time to the matching category value (ReferenceLine needs an exact match);
  // null if the boundary falls outside this match's window
  const fcMs = forecastStart != null ? Date.parse(forecastStart) : NaN;
  const boundary =
    time.find((t) => Date.parse(t) >= fcMs && Date.parse(t) > Date.parse(time[0])) ?? null;
  const showBoundary = boundary != null && Date.parse(boundary) < Date.parse(time[time.length - 1]);

  return (
    <ResponsiveContainer width="100%" height={210}>
      <ComposedChart data={data} margin={{ top: 8, right: 64, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="venueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={meta.color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={meta.color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="t"
          ticks={dayTicks}
          tickFormatter={fmtDate}
          tick={{ fill: "#7c869a", fontSize: 10 }}
          axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
          tickLine={false}
        />
        <YAxis
          width={40}
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => `${Math.round(v)}${meta.unit}`}
          tick={{ fill: "#7c869a", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
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
        {showBoundary && (
          <ReferenceLine
            x={boundary!}
            stroke="#94a3b8"
            strokeDasharray="2 4"
            label={{ value: "forecast", fill: "#94a3b8", fontSize: 10, position: "insideTopLeft" }}
          />
        )}
        <ReferenceLine
          x={kickoff}
          stroke="#facc15"
          strokeDasharray="4 3"
          label={{ value: "kickoff", fill: "#facc15", fontSize: 10, position: "insideTopRight" }}
        />
        {(THRESHOLDS[varKey] ?? []).map((t) => (
          <ReferenceLine key={t.y} y={t.y} stroke="rgba(255,255,255,0.18)" strokeDasharray="3 3" />
        ))}
        {(THRESHOLDS[varKey] ?? []).map((t, i, arr) => {
          // place the label centred in the band above this line (top band: offset up)
          const next = arr[i + 1]?.y;
          const prev = arr[i - 1]?.y;
          const labelY = next != null ? (t.y + next) / 2 : t.y + (t.y - (prev ?? t.y)) / 2;
          return (
            <ReferenceLine
              key={`${t.y}-label`}
              y={labelY}
              stroke="none"
              label={{ value: t.label, position: "right", fill: "#7c869a", fontSize: 9 }}
            />
          );
        })}
        <Area type="monotone" dataKey="venue" name="Venue" stroke={meta.color} strokeWidth={2.4} fill="url(#venueFill)" dot={false} />
        <Line type="monotone" dataKey="a" name={match.stats.team_a.home} stroke="#38bdf8" strokeWidth={1.6} strokeDasharray="5 3" dot={false} />
        <Line type="monotone" dataKey="b" name={match.stats.team_b.home} stroke="#c084fc" strokeWidth={1.6} strokeDasharray="5 3" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
