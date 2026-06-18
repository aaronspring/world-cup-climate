// Perceptual temperature colormap (°C) — cool blue → warm red. Used for pins,
// the legend, and accent colors so the whole UI reads "hot vs cool" at a glance.
const STOPS: [number, [number, number, number]][] = [
  [5, [59, 130, 246]],   // blue
  [15, [34, 211, 238]],  // cyan
  [22, [52, 211, 153]],  // green
  [27, [250, 204, 21]],  // yellow
  [32, [249, 115, 22]],  // orange
  [38, [239, 68, 68]],   // red
  [44, [157, 23, 77]],   // deep magenta
];

export function tempRGB(t: number): [number, number, number] {
  if (t <= STOPS[0][0]) return STOPS[0][1];
  for (let i = 1; i < STOPS.length; i++) {
    if (t <= STOPS[i][0]) {
      const [t0, c0] = STOPS[i - 1];
      const [t1, c1] = STOPS[i];
      const f = (t - t0) / (t1 - t0);
      return [0, 1, 2].map((k) => Math.round(c0[k] + f * (c1[k] - c0[k]))) as [number, number, number];
    }
  }
  return STOPS[STOPS.length - 1][1];
}

export const tempColor = (t: number): string => rgb(tempRGB(t));

const rgb = (c: number[]) => `rgb(${c[0]}, ${c[1]}, ${c[2]})`;

export const TEMP_LEGEND = STOPS.map(([t]) => t);

// Per-country line color (a vivid tone from each flag, lifted for contrast on the
// dark chart background). Keys match `match.team_a`/`match.team_b`. Unknown → gray.
const TEAM_COLORS: Record<string, string> = {
  Algeria: "#2e9e5b", Argentina: "#7cb9e8", Australia: "#ffcd00", Austria: "#ef3340",
  Belgium: "#fdda24", "Bosnia and Herzegovina": "#4f7fff", Brazil: "#2dbe5f",
  Canada: "#ff4136", "Cape Verde": "#3f7fd0", Colombia: "#fcd116", Croatia: "#ff3b30",
  Curacao: "#2563eb", Czechia: "#5a8de0", "DR Congo": "#2da3e0", Ecuador: "#ffd100",
  Egypt: "#e0413f", England: "#ef4444", France: "#4f7fff", Germany: "#ffce00",
  Ghana: "#f5c518", Haiti: "#3b6fd4", Iran: "#2e9e5b", Iraq: "#e0413f",
  "Ivory Coast": "#ff7f27", Japan: "#e63950", Jordan: "#1fae6a", Mexico: "#2dbe5f",
  Morocco: "#d6453f", Netherlands: "#ff7f27", "New Zealand": "#4f7fff", Norway: "#e0413f",
  Panama: "#3b6fd4", Paraguay: "#e0413f", Portugal: "#2dbe5f", Qatar: "#a13858",
  "Saudi Arabia": "#2e9e5b", Scotland: "#4f7fff", Senegal: "#2dbe5f",
  "South Africa": "#2e9e5b", "South Korea": "#4f7fff", Spain: "#ffc400",
  Sweden: "#5a8de0", Switzerland: "#ff4136", Tunisia: "#e63950", Turkiye: "#ef3340",
  USA: "#5a8de0", Uruguay: "#7cb9e8", Uzbekistan: "#2da3e0",
};

export const teamColor = (team: string): string => TEAM_COLORS[team] ?? "#94a3b8";

// Fallback second flag color, used for the away team when both flags share a
// near-identical primary (e.g. Turkiye vs Paraguay, both red). Flag-derived
// where a clear non-white/black second color exists; unlisted → purple accent.
const TEAM_SECONDARY: Record<string, string> = {
  Paraguay: "#3b6fd4", Croatia: "#2f6fd0", Egypt: "#d4af37", Iraq: "#1fae6a",
  Morocco: "#1fae6a", Norway: "#1f5fd0", Germany: "#dd1f26", Belgium: "#ef3340",
  Colombia: "#1f5fd0", Sweden: "#ffcc00", Brazil: "#ffd400", Mexico: "#ef3340",
  Spain: "#c60b1e", Ghana: "#2e9e5b", Senegal: "#ffcc00", Portugal: "#c60b1e",
};

const hexRGB = (h: string): [number, number, number] => [
  parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16),
];
const dist = (a: string, b: string) => {
  const [r1, g1, b1] = hexRGB(a), [r2, g2, b2] = hexRGB(b);
  return Math.hypot(r1 - r2, g1 - g2, b1 - b2);
};

// Colors for a match's home (a) and away (b) lines. If their flag primaries are
// too close to tell apart, the away team falls back to its secondary color.
export function matchColors(a: string, b: string): [string, string] {
  const ca = teamColor(a);
  let cb = teamColor(b);
  if (dist(ca, cb) < 60) cb = TEAM_SECONDARY[b] ?? "#c084fc";
  return [ca, cb];
}

// Neutral gray for the venue series so the flag-colored team lines stand out.
export const VENUE_COLOR = "#94a3b8";
