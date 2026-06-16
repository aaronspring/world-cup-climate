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

export function tempColor(t: number): string {
  if (t <= STOPS[0][0]) return rgb(STOPS[0][1]);
  for (let i = 1; i < STOPS.length; i++) {
    if (t <= STOPS[i][0]) {
      const [t0, c0] = STOPS[i - 1];
      const [t1, c1] = STOPS[i];
      const f = (t - t0) / (t1 - t0);
      return rgb([0, 1, 2].map((k) => Math.round(c0[k] + f * (c1[k] - c0[k]))) as number[]);
    }
  }
  return rgb(STOPS[STOPS.length - 1][1]);
}

const rgb = (c: number[]) => `rgb(${c[0]}, ${c[1]}, ${c[2]})`;

export const TEMP_LEGEND = STOPS.map(([t]) => t);
