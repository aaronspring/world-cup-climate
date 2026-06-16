import type { Cycle, Day, Match } from "./types";

const base = `${import.meta.env.BASE_URL}data`;

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${base}/${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export const loadCycle = () => get<Cycle>("cycles/latest.json");
export const loadDay = (date: string) => get<Day>(`days/${date}.json`);
export const loadMatch = (id: string) => get<Match>(`matches/${id}.json`);
