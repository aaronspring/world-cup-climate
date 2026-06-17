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
  deltaWbgt: string;
  statInfoTexts: {
    deltaTemp: string;
    deltaFeels: string;
    deltaWbgt: string;
    bodyClock: string;
    feelsLike: string;
    wbgtKickoff: string;
  };
  varLabels: Record<string, string>;
  varInfoTexts: Record<string, string>;
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
    tempLegend: "Temperature at kickoff",
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
    deltaWbgt: "Δ WBGT",
    statInfoTexts: {
      deltaTemp: "Air-temperature difference between home city and venue at kickoff. Orange = venue is hotter than home, blue = cooler.",
      deltaFeels: "Heat-index difference between home and venue. Accounts for humidity — a dry 35°C and a humid 30°C can feel equally bad.",
      deltaWbgt: "WBGT difference: the FIFA match-safety index. Combines heat, humidity, wind, and solar radiation. >28°C = cooling breaks possible; >32°C = mandatory.",
      bodyClock: "Approximate time-zone difference between home city and venue (based on longitude). A large jet-lag gap can affect player alertness and recovery.",
      feelsLike: "Heat index at kickoff — combines air temperature and humidity to show how hot it actually feels on the pitch. Above 32°C is considered stressful for athletes.",
      wbgtKickoff: "WBGT (Wet Bulb Globe Temperature) at kickoff — the FIFA match-safety standard. >28°C = cooling breaks possible; >32°C = mandatory.",
    },
    varLabels: {},
    varInfoTexts: {
      t2m: "Air temperature 2 m above the ground. The raw atmospheric reading — doesn't account for wind or humidity.",
      heat_index: "NOAA heat index: how hot it actually feels, combining temperature and humidity. At 35°C with 80% humidity it can feel like 50°C. Meaningful only above ~27°C.",
      humidex: "Environment Canada's official heat-stress scale. Above 40 is dangerous for exercise; above 45 all physical exertion should stop.",
      utci: "Universal Thermal Climate Index (IOC standard for Olympic Games planning). The most comprehensive outdoor comfort index — combines temperature, humidity, wind, and solar radiation.",
      wbgt: "Wet Bulb Globe Temperature — the gold standard for outdoor sports safety. FIFA's cooling-break protocol: >28°C breaks possible, >32°C mandatory under IFAB rules.",
      d2m: "Dewpoint — the temperature at which air becomes saturated. Above 20°C feels muggy; above 25°C is tropical and very taxing for exercise.",
      wind_speed: "Wind speed 10 m above ground (m/s). Below 2 = calm; 5–10 = noticeable breeze that affects play; above 15 = strong wind.",
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
    tempLegend: "Temperatur beim Anstoß",
    close: "Schließen ✕",
    feelsLike: "Gefühlt beim Anstoß",
    airTemp: (t) => `Luft ${t}° · Hitzeindex während des Spiels`,
    home: "Heim",
    deltaTemp: "Δ Temp",
    deltaFeels: "Δ Gefühlt",
    bodyClock: "Jetlag",
    sameTime: "gleiche Zeit",
    vsVenue: "vs. Spielort",
    venueSeries: (label, unit) => `${label} (${unit}) · Spielort (durchgehend) vs. Heimstädte (gestrichelt)`,
    forecast: "Vorhersage",
    kickoff: "Anstoß",
    deltaTemp_tip: "Temperaturdifferenz: Heimatstadt vs. Spielort beim Anstoß. Orange = zu Hause wärmer, blau = kühler.",
    deltaFeels_tip: "Hitzeindex-Differenz: berücksichtigt Luftfeuchtigkeit – wie viel wärmer oder kühler es sich zu Hause im Vergleich zum Spielort anfühlt.",
    feelsLikeTip: "Hitzeindex beim Anstoß – kombiniert Lufttemperatur und Luftfeuchtigkeit. Über 32 °C gilt als belastend für Sportler.",
    deltaWbgt: "Δ WBGT",
    statInfoTexts: {
      deltaTemp: "Temperaturdifferenz zwischen Heimatstadt und Spielort beim Anstoß. Orange = Spielort heißer als zu Hause, blau = kühler.",
      deltaFeels: "Hitzeindex-Differenz zwischen Heimatstadt und Spielort. Berücksichtigt Luftfeuchtigkeit – trockene 35°C und schwüle 30°C können sich gleich schlimm anfühlen.",
      deltaWbgt: "WBGT-Differenz: der FIFA-Sicherheitsindex. Kombiniert Hitze, Luftfeuchtigkeit, Wind und Sonneneinstrahlung. >28°C = Trinkpausen möglich; >32°C = Pflicht.",
      bodyClock: "Ungefähre Zeitzonendifferenz zwischen Heimatstadt und Spielort (längenbasiert). Ein großer Jetlag kann die Aufmerksamkeit und Erholung der Spieler beeinflussen.",
      feelsLike: "Hitzeindex beim Anstoß – kombiniert Lufttemperatur und Luftfeuchtigkeit. Über 32°C gilt als belastend für Sportler.",
      wbgtKickoff: "WBGT (Wet Bulb Globe Temperature) beim Anstoß – der FIFA-Sicherheitsstandard. >28°C = Trinkpausen möglich; >32°C = Pflicht.",
    },
    varLabels: {
      t2m: "Temperatur",
      heat_index: "Gefühlt",
      d2m: "Taupunkt",
    },
    varInfoTexts: {
      t2m: "Lufttemperatur 2 m über dem Boden. Der reine atmosphärische Messwert – ohne Wind- und Feuchtigkeitseinfluss.",
      heat_index: "NOAA-Hitzeindex: wie heiß es sich wirklich anfühlt, kombiniert Temperatur und Luftfeuchtigkeit. Bei 35°C und 80% Luftfeuchtigkeit kann es sich wie 50°C anfühlen.",
      humidex: "Offizielle Hitzestress-Skala von Environment Canada. Über 40 gefährlich für Sport; über 45 sollte jede körperliche Belastung eingestellt werden.",
      utci: "Universal Thermal Climate Index (IOC-Standard für Olympia-Planung). Umfassendstes Außenkomfort-Modell – kombiniert Temperatur, Luftfeuchtigkeit, Wind und Sonnenstrahlung.",
      wbgt: "Wet Bulb Globe Temperature – der Goldstandard für Outdoor-Sportsicherheit. FIFA-Kühlpausenprotokoll: >28°C Pausen möglich, >32°C Pflicht nach IFAB-Regeln.",
      d2m: "Taupunkt – Temperatur, bei der die Luft gesättigt wird. Über 20°C fühlt es sich schwül an; über 25°C ist es tropisch und sehr belastend.",
      wind_speed: "Windgeschwindigkeit 10 m über dem Boden (m/s). Unter 2 = ruhig; 5–10 = spürbarer Wind; über 15 = starker Wind.",
    },
  },
};
