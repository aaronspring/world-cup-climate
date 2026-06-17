import { AnimatePresence, motion } from "framer-motion";
import type { Match, TeamStat, VarMeta } from "./types";
import { flag } from "./flags";
import { tempColor } from "./colors";
import Chart from "./Chart";
import { useLang } from "./LangContext";
import { T, type Translations } from "./i18n";

const sign = (x: number) => { const r = Math.round(x); return r > 0 ? `+${r}` : `${r}`; };
const deltaColor = (x: number) =>
  x > 0.5 ? "text-orange-300" : x < -0.5 ? "text-sky-300" : "text-slate-300";

function TeamColumn({ team, stat, t }: { team: string; stat: TeamStat; t: Translations }) {
  return (
    <div className="flex-1 rounded-2xl bg-white/5 p-3.5">
      <div className="flex items-center gap-2">
        <span className="text-2xl leading-none">{flag(team)}</span>
        <div className="min-w-0">
          <div className="truncate font-semibold">{team}</div>
          <div className="truncate text-xs text-slate-400">{t.home} · {stat.home}</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-1.5 text-center">
        <Stat label={t.deltaTemp} value={`${sign(stat.d_t2m)}°`} cls={deltaColor(stat.d_t2m)} tip={t.deltaTemp_tip} />
        <Stat label={t.deltaFeels} value={`${sign(stat.d_heat_index)}°`} cls={deltaColor(stat.d_heat_index)} tip={t.deltaFeels_tip} />
        <Stat label={t.bodyClock} value={stat.tz_diff_h === 0 ? "0h" : `${sign(stat.tz_diff_h)}h`} cls="text-violet-300" />
      </div>
    </div>
  );
}

function Stat({ label, value, cls, tip }: { label: string; value: string; cls: string; tip?: string }) {
  return (
    <div className="rounded-xl bg-black/20 px-1 py-2" title={tip}>
      <div className={`text-lg font-bold tabular-nums ${cls}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}

export default function MatchCard({
  match,
  variables,
  varKey,
  setVarKey,
  forecastStart,
  onClose,
}: {
  match: Match | null;
  variables: Record<string, VarMeta>;
  varKey: string;
  setVarKey: (k: string) => void;
  forecastStart: string | null;
  onClose: () => void;
}) {
  const [lang] = useLang();
  const t = T[lang];

  return (
    <AnimatePresence>
      {match && (
        <motion.aside
          key={match.id}
          initial={{ x: "100%", opacity: 0.4 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: "100%", opacity: 0 }}
          transition={{ type: "spring", stiffness: 320, damping: 34 }}
          className="glass scroll-thin absolute right-0 top-0 z-20 flex h-full w-full flex-col gap-4 overflow-y-auto rounded-l-3xl p-5 shadow-2xl sm:w-[420px]"
        >
          <div className="flex items-start justify-between gap-2">
            <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-medium text-slate-300">
              {match.stage}
            </span>
            <button
              onClick={onClose}
              className="rounded-full bg-white/10 px-3 py-1 text-sm text-slate-300 transition hover:bg-white/20"
            >
              {t.close}
            </button>
          </div>

          <div>
            <div className="flex items-center gap-2 text-xl font-extrabold">
              <span>{flag(match.team_a)}</span>
              <span className="truncate">{match.team_a}</span>
              <span className="text-slate-500">v</span>
              <span>{flag(match.team_b)}</span>
              <span className="truncate">{match.team_b}</span>
            </div>
            <div className="mt-1 text-sm text-slate-400">
              {match.venue.stadium} · {match.venue.city}
            </div>
            <div className="text-sm text-slate-400">
              {t.kickoff.charAt(0).toUpperCase() + t.kickoff.slice(1)} {match.kickoff_local} local
            </div>
          </div>

          <div className="flex items-center gap-3 rounded-2xl bg-white/5 p-4" title={t.feelsLikeTip}>
            <div
              className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl text-2xl font-extrabold text-black"
              style={{ background: tempColor(match.heat_index_at_kickoff) }}
            >
              {Math.round(match.heat_index_at_kickoff)}°
            </div>
            <div>
              <div className="text-sm font-semibold">{t.feelsLike}</div>
              <div className="text-xs text-slate-400">{t.airTemp(Math.round(match.t2m_at_kickoff))}</div>
            </div>
          </div>

          <div className="flex gap-3">
            <TeamColumn team={match.team_a} stat={match.stats.team_a} t={t} />
            <TeamColumn team={match.team_b} stat={match.stats.team_b} t={t} />
          </div>

          <div>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {Object.entries(variables).map(([k, m]) => (
                <button
                  key={k}
                  onClick={() => setVarKey(k)}
                  title={t.varTips[k]}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                    k === varKey
                      ? "bg-white text-slate-900"
                      : "bg-white/10 text-slate-300 hover:bg-white/20"
                  }`}
                >
                  {t.varLabels[k] ?? m.label}
                </button>
              ))}
            </div>
            <div className="rounded-2xl bg-black/20 p-3">
              <div className="mb-1 px-1 text-xs text-slate-400">
                {t.venueSeries(t.varLabels[varKey] ?? variables[varKey].label, variables[varKey].unit)}
              </div>
              <Chart match={match} varKey={varKey} meta={variables[varKey]} forecastStart={forecastStart} />
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
