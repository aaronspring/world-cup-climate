import type { Day } from "./types";

export interface NextMatchRef {
  date: string;
  id: string;
}

// Pick the soonest match whose kickoff is at or after `nowIso`, across the
// given days. kickoff_utc is a zero-padded UTC ISO string, so lexical compares
// match chronological order. A match's `date` key (venue-local) can lag its
// kickoff_utc by a few hours (late-night kickoffs roll into the next UTC day),
// so callers should feed the day before "today" too. Returns null when every
// match is in the past.
export function pickNextMatch(days: Day[], nowIso: string): NextMatchRef | null {
  let best: { date: string; id: string; kickoff_utc: string } | null = null;
  for (const day of days) {
    for (const m of day.matches) {
      if (m.kickoff_utc >= nowIso && (!best || m.kickoff_utc < best.kickoff_utc)) {
        best = { date: m.date, id: m.id, kickoff_utc: m.kickoff_utc };
      }
    }
  }
  return best ? { date: best.date, id: best.id } : null;
}

// Shift an ISO date (YYYY-MM-DD) by `deltaDays`, staying in UTC.
const shiftDate = (isoDate: string, deltaDays: number): string => {
  const d = new Date(isoDate + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + deltaDays);
  return d.toISOString().slice(0, 10);
};

// Candidate date keys to inspect when looking for the next match: from the day
// before "today" onward, so a late kickoff keyed to the previous local day is
// not missed. Returns dates in their original (sorted) order.
export function candidateDates(dates: string[], nowIso: string): string[] {
  const from = shiftDate(nowIso.slice(0, 10), -1);
  return dates.filter((d) => d >= from);
}
