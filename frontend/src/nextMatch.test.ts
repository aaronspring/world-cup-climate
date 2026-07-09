import { describe, expect, it } from "vitest";
import { candidateDates, pickNextMatch } from "./nextMatch";
import type { Day, Pin } from "./types";

const pin = (id: string, date: string, kickoff_utc: string): Pin => ({
  id,
  date,
  stage: "Group A",
  kickoff_utc,
  kickoff_local: kickoff_utc,
  team_a: "A",
  team_b: "B",
  venue: { key: "v", stadium: "S", city: "C", country: "X", lat: 0, lon: 0 },
  t2m_at_kickoff: null,
  heat_index_at_kickoff: null,
});

const day = (date: string, pins: Pin[]): Day => ({ date, matches: pins });

describe("pickNextMatch", () => {
  it("returns the soonest match at or after now", () => {
    const days = [
      day("2026-06-28", [
        pin("m1", "2026-06-28", "2026-06-28T16:00:00Z"),
        pin("m2", "2026-06-28", "2026-06-28T19:00:00Z"),
      ]),
      day("2026-06-29", [pin("m3", "2026-06-29", "2026-06-29T19:00:00Z")]),
    ];
    expect(pickNextMatch(days, "2026-06-28T17:00:00Z")).toEqual({
      date: "2026-06-28",
      id: "m2",
    });
  });

  it("treats a kickoff exactly at now as upcoming", () => {
    const days = [day("2026-06-28", [pin("m1", "2026-06-28", "2026-06-28T19:00:00Z")])];
    expect(pickNextMatch(days, "2026-06-28T19:00:00Z")).toEqual({
      date: "2026-06-28",
      id: "m1",
    });
  });

  it("picks the earliest kickoff even when day keys are out of order", () => {
    // A late local kickoff keyed to the previous day rolls into the next UTC day,
    // landing before a match keyed to that later day.
    const days = [
      day("2026-06-29", [pin("late", "2026-06-29", "2026-06-30T01:00:00Z")]),
      day("2026-06-30", [pin("early", "2026-06-30", "2026-06-30T16:00:00Z")]),
    ];
    expect(pickNextMatch(days, "2026-06-29T23:00:00Z")?.id).toBe("late");
  });

  it("returns null when every match is in the past", () => {
    const days = [day("2026-06-28", [pin("m1", "2026-06-28", "2026-06-28T16:00:00Z")])];
    expect(pickNextMatch(days, "2026-06-28T20:00:00Z")).toBeNull();
  });
});

describe("candidateDates", () => {
  const dates = ["2026-06-26", "2026-06-27", "2026-06-28", "2026-06-29"];

  it("includes the day before today to catch cross-midnight kickoffs", () => {
    expect(candidateDates(dates, "2026-06-28T12:00:00Z")).toEqual([
      "2026-06-27",
      "2026-06-28",
      "2026-06-29",
    ]);
  });

  it("handles month boundaries", () => {
    expect(candidateDates(["2026-06-30", "2026-07-01"], "2026-07-01T00:00:00Z")).toEqual([
      "2026-06-30",
      "2026-07-01",
    ]);
  });
});
