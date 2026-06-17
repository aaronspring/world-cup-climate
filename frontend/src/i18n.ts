export type Lang = "en" | "de";

export const LOCALE: Record<Lang, string> = { en: "en-US", de: "de-DE" };

export interface Translations {
  title: string;
  ecmwf: string;
  demoData: string;
  errorTitle: string;
  errorCmd: string;
  errorCmdSuffix: string;
  matchCount: (n: number, day: number) => string;
  tempLegend: string;
  close: string;
  feelsLike: string;
  airTemp: (t: number) => string;
  home: string;
  deltaTemp: string;
  deltaFeels: string;
  bodyClock: string;
  sameTime: string;
  vsVenue: string;
  venueSeries: (label: string, unit: string) => string;
  forecast: string;
  kickoff: string;
  deltaTemp_tip: string;
  deltaFeels_tip: string;
  feelsLikeTip: string;
  varTips: Record<string, string>;
}

export const T: Record<Lang, Translations> = {
  en: {
    title: "World Cup 2026 · Match Climate",
    ecmwf: "ECMWF forecast",
    demoData: "demo data",
    errorTitle: "Couldn't load forecast data",
    errorCmd: "Run",
    errorCmdSuffix: "first.",
    matchCount: (n, day) => `${n} matches · Jun ${day}`,
    tempLegend: "Temp at kickoff",
    close: "close ✕",
    feelsLike: "Feels like at kickoff",
    airTemp: (t) => `Air ${t}° · heat-index over the match window`,
    home: "home",
    deltaTemp: "Δ temp",
    deltaFeels: "Δ feels",
    bodyClock: "body clock",
    sameTime: "same time",
    vsVenue: "vs venue",
    venueSeries: (label, unit) => `${label} (${unit}) · venue (solid) vs home cities (dashed)`,
    forecast: "forecast",
    kickoff: "kickoff",
    deltaTemp_tip: "Air temperature difference: home city vs. venue around kickoff. Orange = hotter at home, blue = cooler.",
    deltaFeels_tip: "Heat-index difference: accounts for humidity — how much hotter or cooler it feels at home vs. the venue.",
    feelsLikeTip: "Heat index at kickoff — combines air temperature and humidity to show how hot it actually feels to players on the pitch. Above 32°C is considered stressful for athletes.",
    varTips: {
      t2m: "Air temperature 2 m above ground (°C)",
      heat_index: "Feels like — combines air temperature and humidity to estimate perceived heat stress",
      d2m: "Dewpoint — the temperature at which air becomes saturated; higher dewpoint = more humid and muggy",
    },
  },
  de: {
    title: "WM 2026 · Spielklima",
    ecmwf: "ECMWF-Vorhersage",
    demoData: "Demo-Daten",
    errorTitle: "Vorhersagedaten konnten nicht geladen werden",
    errorCmd: "Zuerst ausführen:",
    errorCmdSuffix: "",
    matchCount: (n, day) => `${n} Spiele · Jun ${day}`,
    tempLegend: "Temp beim Anstoß",
    close: "Schließen ✕",
    feelsLike: "Gefühlt beim Anstoß",
    airTemp: (t) => `Luft ${t}° · Hitzeindex während des Spiels`,
    home: "Heim",
    deltaTemp: "Δ Temp",
    deltaFeels: "Δ Gefühlt",
    bodyClock: "Jetlag",
    sameTime: "gleiche Zeit",
    vsVenue: "vs. Spielort",
    venueSeries: (label, unit) => `${label} (${unit}) · Spielort (ausgezogen) vs. Heimstädte (gestrichelt)`,
    forecast: "Vorhersage",
    kickoff: "Anstoß",
    deltaTemp_tip: "Temperaturdifferenz: Heimatstadt vs. Spielort beim Anstoß. Orange = zu Hause wärmer, blau = kühler.",
    deltaFeels_tip: "Hitzeindex-Differenz: berücksichtigt Luftfeuchtigkeit – wie viel wärmer oder kühler es sich zu Hause im Vergleich zum Spielort anfühlt.",
    feelsLikeTip: "Hitzeindex beim Anstoß – kombiniert Lufttemperatur und Luftfeuchtigkeit. Über 32 °C gilt als belastend für Sportler.",
    varTips: {
      t2m: "Lufttemperatur 2 m über dem Boden (°C)",
      heat_index: "Gefühlt – kombiniert Lufttemperatur und Luftfeuchtigkeit zur Schätzung der Wärmebelastung",
      d2m: "Taupunkt – Temperatur, bei der die Luft gesättigt wird; höherer Taupunkt = schwüler",
    },
  },
};
