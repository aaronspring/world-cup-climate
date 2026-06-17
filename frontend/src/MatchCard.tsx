import { useState } from "react";
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

// ── InfoTooltip ──────────────────────────────────────────────────────────────

interface TooltipInfo { text: string; href: string }

function InfoTooltip({ text, href }: TooltipInfo) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex shrink-0">
      <span
        role="button"
        tabIndex={0}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className="cursor-help px-0.5 text-[11px] leading-none opacity-70 hover:opacity-100 focus:outline-none"
        aria-label="More information"
      >
        ⓘ
      </span>
      {open && (
        <span
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          className="pointer-events-auto absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-xl bg-slate-900 px-3.5 py-3 text-xs leading-relaxed text-slate-200 shadow-2xl ring-1 ring-white/10"
        >
          {text}
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="mt-2 flex items-center gap-1 font-medium text-sky-400 hover:text-sky-300 hover:underline"
          >
            xclim docs ↗
          </a>
        </span>
      )}
    </span>
  );
}

// hrefs are language-neutral; text comes from translations
const VAR_INFO_HREF: Record<string, string> = {
  t2m:        "https://xclim.readthedocs.io/en/stable/",
  heat_index: "https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.heat_index",
  humidex:    "https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.humidex",
  utci:       "https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.universal_thermal_climate_index",
  wbgt:       "https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.wet_bulb_globe_temperature",
  d2m:        "https://xclim.readthedocs.io/en/stable/",
  wind_speed: "https://xclim.readthedocs.io/en/stable/",
};

// ── Stat tile ────────────────────────────────────────────────────────────────

function Stat({ label, value, cls, info }: { label: string; value: string; cls: string; info?: TooltipInfo }) {
  return (
    <div className="rounded-xl bg-black/20 px-1 py-2">
      <div className={`text-lg font-bold tabular-nums ${cls}`}>{value}</div>
      <div className="flex items-center justify-center gap-0.5 text-[10px] uppercase tracking-wide text-slate-500">
        {label}
        {info && <InfoTooltip {...info} />}
      </div>
    </div>
  );
}

// ── Team column ──────────────────────────────────────────────────────────────

function TeamColumn({ team, stat }: { team: string; stat: TeamStat }) {
  const [lang] = useLang();
  const t = T[lang];
  const si = t.statInfoTexts;
  const tz = stat.tz_diff_h === 0 ? t.sameTime : `${sign(stat.tz_diff_h)}h ${t.vsVenue}`;
  const hasWbgt = stat.d_wbgt != null;

  return (
    <div className="flex-1 rounded-2xl bg-white/5 p-3.5">
      <div className="flex items-center gap-2">
        <span className="text-2xl leading-none">{flag(team)}</span>
        <div className="min-w-0">
          <div className="truncate font-semibold">{team}</div>
          <div className="truncate text-xs text-slate-400">{t.home} · {stat.home}</div>
        </div>
      </div>
      <div className={`mt-3 grid gap-1.5 text-center ${hasWbgt ? "grid-cols-2" : "grid-cols-3"}`}>
        <Stat
          label={t.deltaTemp}
          value={`${sign(stat.d_t2m)}°`}
          cls={deltaColor(stat.d_t2m)}
          info={{ text: si.deltaTemp, href: "https://xclim.readthedocs.io/en/stable/" }}
        />
        <Stat
          label={t.deltaFeels}
          value={`${sign(stat.d_heat_index)}°`}
          cls={deltaColor(stat.d_heat_index)}
          info={{ text: si.deltaFeels, href: "https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.heat_index" }}
        />
        {hasWbgt ? (
          <Stat
            label={t.deltaWbgt}
            value={`${sign(stat.d_wbgt!)}°`}
            cls={deltaColor(stat.d_wbgt!)}
            info={{ text: si.deltaWbgt, href: "https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.wet_bulb_globe_temperature" }}
          />
        ) : (
          <Stat
            label={t.bodyClock}
            value={tz === t.sameTime ? "0h" : `${sign(stat.tz_diff_h)}h`}
            cls="text-violet-300"
            info={{ text: si.bodyClock, href: "https://xclim.readthedocs.io/en/stable/" }}
          />
        )}
        {hasWbgt && (
          <Stat
            label={t.bodyClock}
            value={tz === t.sameTime ? "0h" : `${sign(stat.tz_diff_h)}h`}
            cls="text-violet-300"
            info={{ text: si.bodyClock, href: "https://xclim.readthedocs.io/en/stable/" }}
          />
        )}
      </div>
    </div>
  );
}

// ── MatchCard ────────────────────────────────────────────────────────────────

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
  const t: Translations = T[lang];
  const si = t.statInfoTexts;

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

          {/* Kickoff hero tile */}
          <div className="flex items-center gap-3 rounded-2xl bg-white/5 p-4">
            <div
              className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl text-2xl font-extrabold text-black"
              style={{ background: tempColor(match.heat_index_at_kickoff) }}
            >
              {Math.round(match.heat_index_at_kickoff)}°
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1 text-sm font-semibold">
                {t.feelsLike}
                <InfoTooltip
                  text={si.feelsLike}
                  href="https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.heat_index"
                />
              </div>
              <div className="text-xs text-slate-400">
                {t.airTemp(Math.round(match.t2m_at_kickoff))}
                {match.wbgt_at_kickoff != null && (
                  <span className="ml-2">
                    · WBGT {Math.round(match.wbgt_at_kickoff)}°
                    <InfoTooltip
                      text={si.wbgtKickoff}
                      href="https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.wet_bulb_globe_temperature"
                    />
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-3">
            <TeamColumn team={match.team_a} stat={match.stats.team_a} />
            <TeamColumn team={match.team_b} stat={match.stats.team_b} />
          </div>

          {/* Chart variable selector */}
          <div>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {Object.entries(variables).map(([k, m]) => (
                <button
                  key={k}
                  onClick={() => setVarKey(k)}
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition ${
                    k === varKey
                      ? "bg-white text-slate-900"
                      : "bg-white/10 text-slate-300 hover:bg-white/20"
                  }`}
                >
                  {t.varLabels[k] ?? m.label}
                  {VAR_INFO_HREF[k] && t.varInfoTexts[k] && (
                    <InfoTooltip text={t.varInfoTexts[k]} href={VAR_INFO_HREF[k]} />
                  )}
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
