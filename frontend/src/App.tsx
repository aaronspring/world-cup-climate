import { useEffect, useMemo, useState } from "react";
import MapView from "./MapView";
import MatchCard from "./MatchCard";
import { loadCycle, loadDay, loadMatch } from "./data";
import type { Cycle, Match, Pin } from "./types";
import { flag } from "./flags";
import { tempColor, TEMP_LEGEND } from "./colors";
import { useLang } from "./LangContext";
import { T, LOCALE } from "./i18n";

const wd = (d: string, locale: string) =>
  new Date(d + "T00:00:00Z").toLocaleDateString(locale, { weekday: "short", timeZone: "UTC" });
const dayNum = (d: string) => new Date(d + "T00:00:00Z").getUTCDate();

export default function App() {
  const [lang, setLang] = useLang();
  const t = T[lang];
  const locale = LOCALE[lang];

  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [date, setDate] = useState<string>("");
  const [pins, setPins] = useState<Pin[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [match, setMatch] = useState<Match | null>(null);
  const [varKey, setVarKey] = useState("t2m");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCycle()
      .then((c) => {
        setCycle(c);
        const today = new Date().toISOString().slice(0, 10);
        setDate(c.dates.includes(today) ? today : c.dates[0]);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!date) return;
    setSelId(null);
    setMatch(null);
    loadDay(date).then((d) => setPins(d.matches)).catch((e) => setError(String(e)));
  }, [date]);

  useEffect(() => {
    if (!selId) return setMatch(null);
    let live = true;
    loadMatch(selId).then((m) => live && setMatch(m)).catch((e) => setError(String(e)));
    return () => { live = false; };
  }, [selId]);

  const sortedPins = useMemo(
    () => [...pins].sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc)),
    [pins],
  );

  const overlayMap = useMemo(
    () => (selId ? sortedPins.find((p) => p.id === selId) : sortedPins[0])?.t2m_map ?? null,
    [selId, sortedPins],
  );

  if (error)
    return (
      <div className="grid h-full place-items-center p-8 text-center text-slate-400">
        <div>
          <div className="mb-2 text-lg font-semibold text-slate-200">{t.errorTitle}</div>
          <div className="mt-3 text-xs">
            {t.errorCmd} <code className="text-slate-300">uv run python backend/recompute.py</code>{t.errorCmdSuffix ? ` ${t.errorCmdSuffix}` : ""}
          </div>
        </div>
      </div>
    );

  return (
    <div className="relative h-dvh w-screen overflow-hidden">
      <MapView pins={sortedPins} selectedId={selId} onSelect={setSelId} overlayMap={overlayMap} />

      {/* Header */}
      <header className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-col gap-2 p-3 sm:p-4">
        <div className="glass pointer-events-auto flex items-center gap-3 self-start rounded-2xl px-4 py-2.5">
          <span className="text-xl">⚽</span>
          <div className="leading-tight">
            <div className="font-extrabold tracking-tight">{t.title}</div>
            <div className="text-[11px] text-slate-400">
              <a
                href="https://app.earthmover.io/marketplace/6971be98fc964a0d0fb66e04"
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-slate-600 hover:text-slate-200"
                title="ECMWF IFS — the European Centre for Medium-Range Weather Forecasts global model. Updated every 6 hours (00, 06, 12, 18 UTC). Free open dataset via Earthmover Arraylake."
              >
                {t.ecmwf}
              </a>
              {cycle ? ` · ${t.cycleLabel} ${cycle.cycle.slice(0, 13)}h` : ""}
              {cycle?.source === "demo" ? ` · ${t.demoData}` : ""}
            </div>
          </div>
        </div>

        {/* Date strip */}
        <div className="glass scroll-thin pointer-events-auto flex max-w-full gap-1.5 self-start overflow-x-auto rounded-2xl p-1.5">
          {cycle?.dates.map((d) => (
            <button
              key={d}
              onClick={() => setDate(d)}
              className={`flex shrink-0 flex-col items-center rounded-xl px-3 py-1.5 text-center transition ${
                d === date ? "bg-white text-slate-900" : "text-slate-300 hover:bg-white/10"
              }`}
            >
              <span className="text-[10px] uppercase opacity-70">{wd(d, locale)}</span>
              <span className="text-base font-bold leading-none">{dayNum(d)}</span>
            </button>
          ))}
        </div>
      </header>

      {/* Match list */}
      <aside
        className={`glass scroll-thin absolute left-3 top-32 z-10 hidden max-h-[calc(100%-10rem)] w-72 overflow-y-auto rounded-2xl p-2 sm:top-36 sm:block ${
          match ? "lg:block" : ""
        }`}
      >
        <div className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
          {t.matchCount(sortedPins.length, dayNum(date))}
        </div>
        {sortedPins.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelId(p.id)}
            className={`flex w-full items-center gap-2.5 rounded-xl px-2 py-2 text-left transition ${
              p.id === selId ? "bg-white/15" : "hover:bg-white/8"
            }`}
          >
            <span
              className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-xs font-bold text-black"
              style={{ background: tempColor(p.t2m_at_kickoff) }}
            >
              {Math.round(p.t2m_at_kickoff)}°
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">
                {flag(p.team_a)} {p.team_a} <span className="text-slate-500">v</span> {flag(p.team_b)} {p.team_b}
              </div>
              <div className="truncate text-xs text-slate-400">
                {p.venue.city} · {p.kickoff_local.slice(11)}
              </div>
            </div>
          </button>
        ))}
      </aside>

      {/* Bottom-left: legend + language picker */}
      <div className="absolute bottom-3 left-3 z-10 flex flex-col gap-2">
        {/* Language picker */}
        <div className="glass flex gap-1 self-start rounded-xl px-2 py-1.5">
          {(["en", "de"] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`rounded-lg px-2 py-0.5 text-xs font-semibold transition ${
                l === lang ? "bg-white text-slate-900" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {l === "en" ? "🇬🇧 EN" : "🇩🇪 DE"}
            </button>
          ))}
        </div>

        {/* Temperature legend */}
        <div className="glass rounded-xl px-3 py-2">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-400">{t.tempLegend}</div>
          <div className="flex items-center gap-2">
            <div
              className="h-2.5 w-40 rounded-full"
              style={{
                background: `linear-gradient(90deg, ${TEMP_LEGEND.map((t) => tempColor(t)).join(", ")})`,
              }}
            />
          </div>
          <div className="mt-0.5 flex justify-between text-[10px] text-slate-500">
            <span>{TEMP_LEGEND[0]}°</span>
            <span>{TEMP_LEGEND[TEMP_LEGEND.length - 1]}°</span>
          </div>
        </div>
      </div>

      <MatchCard
        match={match}
        variables={cycle?.variables ?? {}}
        varKey={varKey}
        setVarKey={setVarKey}
        forecastStart={cycle?.cycle ?? null}
        onClose={() => setSelId(null)}
      />
    </div>
  );
}
