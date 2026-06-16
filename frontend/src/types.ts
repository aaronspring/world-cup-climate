// Shared data contract — mirrors backend/recompute.py output.

export interface VarMeta {
  label: string;
  unit: string;
  color: string;
}

export interface Cycle {
  cycle: string;
  source: string;
  generated_at: string;
  dates: string[];
  variables: Record<string, VarMeta>;
}

export interface Venue {
  key: string;
  stadium: string;
  city: string;
  country: string;
  lat: number;
  lon: number;
}

export interface Pin {
  id: string;
  date: string;
  stage: string;
  kickoff_utc: string;
  kickoff_local: string;
  team_a: string;
  team_b: string;
  venue: Venue;
  t2m_at_kickoff: number;
  heat_index_at_kickoff: number;
}

export interface Day {
  date: string;
  matches: Pin[];
}

export interface TeamStat {
  home: string;
  country: string;
  tz_diff_h: number;
  d_t2m: number;
  d_d2m: number;
  d_heat_index: number;
}

export type SeriesVars = Record<string, number[]>;

export interface Match extends Pin {
  window: { start: string; end: string };
  series: {
    time: string[];
    venue: SeriesVars;
    team_a: SeriesVars;
    team_b: SeriesVars;
  };
  stats: { team_a: TeamStat; team_b: TeamStat };
}
