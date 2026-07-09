import { useRef, useState } from "react";
import { createPortal } from "react-dom";
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

interface TooltipInfo { text: string; href?: string; linkLabel?: string }

const TIP_W = 256; // w-64
function InfoTooltip({ text, href, linkLabel }: TooltipInfo) {
  const [pos, setPos] = useState<{ left: number; bottom: number } | null>(null);
  const iconRef = useRef<HTMLSpanElement>(null);
  // ponytail: 0.5s close delay so the mouse can cross the gap to click the link
  const closeTimer = useRef<ReturnType<typeof setTimeout>>();
  const cancelClose = () => clearTimeout(closeTimer.current);
  const scheduleClose = () => { cancelClose(); closeTimer.current = setTimeout(() => setPos(null), 500); };
  // ponytail: fixed-position portal + viewport clamp so the tip never clips on
  // the card's overflow-hidden edge nor spills off-screen
  const place = () => {
    const r = iconRef.current?.getBoundingClientRect();
    if (!r) return;
    const left = Math.min(Math.max(8, r.left + r.width / 2 - TIP_W / 2), window.innerWidth - TIP_W - 8);
    setPos({ left, bottom: window.innerHeight - r.top + 8 });
  };
  return (
    <span className="relative inline-flex shrink-0">
      <span
        ref={iconRef}
        role="button"
        tabIndex={0}
        onMouseEnter={() => { cancelClose(); place(); }}
        onMouseLeave={scheduleClose}
        onClick={(e) => { e.stopPropagation(); pos ? setPos(null) : place(); }}
        className="cursor-help px-0.5 text-[11px] leading-none opacity-70 hover:opacity-100 focus:outline-none"
        aria-label="More information"
      >
        ⓘ
      </span>
      {pos && createPortal(
        <span
          onMouseEnter={cancelClose}
          onMouseLeave={scheduleClose}
          style={{ left: pos.left, bottom: pos.bottom, width: TIP_W }}
          className="pointer-events-auto fixed z-50 rounded-xl bg-slate-900 px-3.5 py-3 text-xs leading-relaxed text-slate-200 shadow-2xl ring-1 ring-white/10"
        >
          {text}
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="mt-2 flex items-center gap-1 font-medium text-sky-400 hover:text-sky-300 hover:underline"
            >
              {linkLabel ?? "xclim docs"} ↗
            </a>
          )}
        </span>,
        document.body,
      )}
    </span>
  );
}

// Source link per index — language-neutral. xclim docs only where the index is
// actually computed with xclim (humidex, utci); others cite their real source.
// Raw variables (t2m, d2m, wind_speed) have no derived-index source → no link.
const XCLIM = (anchor: string): TooltipInfo["href"] =>
  `https://xclim.readthedocs.io/en/stable/indices.html#xclim.indices.${anchor}`;
const NOAA_HI = { href: "https://www.weather.gov/media/ffc/ta_htindx.PDF", linkLabel: "NOAA" };
const STULL_WBGT = { href: "https://doi.org/10.1175/JAMC-D-11-0143.1", linkLabel: "Stull 2011" };
// FIFA's official player-welfare / heat statement for the 2026 tournament.
const FIFA_HEAT = {
  href: "https://inside.fifa.com/organisation/news/hydration-breaks-world-cup-2026-player-welfare",
  linkLabel: "FIFA",
};

const VAR_SOURCE: Record<string, { href?: string; linkLabel?: string }> = {
  t2m:        {},
  heat_index: NOAA_HI,
  humidex:    { href: XCLIM("humidex") },
  utci:       { href: XCLIM("universal_thermal_climate_index") },
  wbgt:       STULL_WBGT,
  d2m:        {},
  wind_speed: {},
};

// ── Stat tile ────────────────────────────────────────────────────────────────

function Stat({ label, value, cls, info }: { label: string; value: string; cls: string; info?: TooltipInfo }) {
  return (
    <div className="rounded-xl bg-black/20 px-1 py-2">
      <div className={`text-lg font-bold tabular-nums ${cls}`}>{value}</div>
      <div className="flex items-center justify-center gap-0.5 text-[10px] tracking-wide text-slate-500">
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
          info={{ text: si.deltaTemp }}
        />
        <Stat
          label={t.deltaFeels}
          value={`${sign(stat.d_heat_index)}°`}
          cls={deltaColor(stat.d_heat_index)}
          info={{ text: si.deltaFeels, ...NOAA_HI }}
        />
        {hasWbgt && (
          <Stat
            label={t.deltaWbgt}
            value={`${sign(stat.d_wbgt!)}°`}
            cls={deltaColor(stat.d_wbgt!)}
            info={{ text: si.deltaWbgt, ...STULL_WBGT }}
          />
        )}
        <Stat
          label={t.bodyClock}
          value={`${sign(stat.tz_diff_h)}h`}
          cls="text-violet-300"
          info={{ text: si.bodyClock }}
        />
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
  // Beyond the forecast horizon (far-future knockout fixture): no IFS data yet.
  const pending = match?.t2m_at_kickoff == null;

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
          <div className="flex items-start justify-between gap-2 pr-12">
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
            <div className="mt-1 flex items-center gap-1 text-sm text-slate-400">
              <span className="truncate">{match.venue.stadium} · {match.venue.city}</span>
              {match.venue.air_conditioned && (
                <span className="inline-flex shrink-0 items-center" aria-label={t.airConLabel} title={t.airConLabel}>
                  ❄️
                  <InfoTooltip text={t.airConTip} {...FIFA_HEAT} />
                </span>
              )}
            </div>
            <div className="text-sm text-slate-400">
              {t.kickoff.charAt(0).toUpperCase() + t.kickoff.slice(1)} {match.kickoff_local} {t.localTime}
            </div>
          </div>

          {/* Kickoff hero tile */}
          {pending ? (
            <div className="flex items-center gap-3 rounded-2xl bg-white/5 p-4">
              <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-slate-600/40 text-2xl font-extrabold text-slate-300">
                —
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{t.forecastPending}</div>
                <div className="text-xs text-slate-400">{t.forecastPendingNote}</div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 rounded-2xl bg-white/5 p-4">
              <div
                className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl text-2xl font-extrabold text-black"
                style={{ background: tempColor(match.heat_index_at_kickoff!) }}
              >
                {Math.round(match.heat_index_at_kickoff!)}°
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1 text-sm font-semibold">
                  {t.feelsLike}
                  <InfoTooltip text={si.feelsLike} {...NOAA_HI} />
                </div>
                <div className="text-xs text-slate-400">
                  {t.airTemp(Math.round(match.t2m_at_kickoff!))}
                  {match.wbgt_at_kickoff != null && (
                    <span className="ml-2">
                      · WBGT {Math.round(match.wbgt_at_kickoff)}°
                      <InfoTooltip text={si.wbgtKickoff} {...STULL_WBGT} />
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {match.stats.team_a || match.stats.team_b ? (
            <div className="flex gap-3">
              {match.stats.team_a && <TeamColumn team={match.team_a} stat={match.stats.team_a} />}
              {match.stats.team_b && <TeamColumn team={match.team_b} stat={match.stats.team_b} />}
            </div>
          ) : (
            <div className="rounded-2xl bg-white/5 px-3.5 py-3 text-sm text-slate-400">
              {t.knockoutTbd}
            </div>
          )}

          {/* Chart variable selector — hidden when the forecast is pending */}
          {pending ? (
            <div className="rounded-2xl bg-black/20 px-3.5 py-6 text-center text-sm text-slate-400">
              {t.forecastPendingNote}
            </div>
          ) : (
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
                  {t.varInfoTexts[k] && (
                    <InfoTooltip text={t.varInfoTexts[k]} {...VAR_SOURCE[k]} />
                  )}
                </button>
              ))}
            </div>
            <div className="rounded-2xl bg-black/20 p-3">
              <div className="mb-1 px-1 text-xs text-slate-400">
                {(match.series.team_a || match.series.team_b ? t.venueSeries : t.venueOnlySeries)(
                  t.varLabels[varKey] ?? variables[varKey].label,
                  variables[varKey].unit,
                )}
              </div>
              <Chart match={match} varKey={varKey} meta={variables[varKey]} forecastStart={forecastStart} />
            </div>
          </div>
          )}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
