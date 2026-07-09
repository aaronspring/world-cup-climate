export type Lang = "en" | "de";

export const LOCALE: Record<Lang, string> = { en: "en-US", de: "de-DE" };

export interface Translations {
  title: string;
  ecmwf: string;
  cycleLabel: string;
  demoData: string;
  errorTitle: string;
  errorCmd: string;
  errorCmdSuffix: string;
  matchCount: (n: number, when: string) => string;
  tempLegend: string;
  close: string;
  feelsLike: string;
  airTemp: (t: number) => string;
  home: string;
  deltaTemp: string;
  deltaFeels: string;
  bodyClock: string;
  venueSeries: (label: string, unit: string) => string;
  venueOnlySeries: (label: string, unit: string) => string;
  knockoutTbd: string;
  forecastPending: string;
  forecastPendingNote: string;
  forecast: string;
  kickoff: string;
  localTime: string;
  deltaWbgt: string;
  airConLabel: string;
  airConTip: string;
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
  chart: { venue: string; thresholds: Record<string, string> };
}

export const T: Record<Lang, Translations> = {
  en: {
    title: "World Cup 2026 · Match Climate",
    ecmwf: "ECMWF forecast",
    cycleLabel: "Forecast Reference Time",
    demoData: "demo data",
    errorTitle: "Couldn't load forecast data",
    errorCmd: "Run",
    errorCmdSuffix: "first.",
    matchCount: (n, when) => `${n} matches · ${when}`,
    tempLegend: "Temperature at kickoff",
    close: "close ✕",
    feelsLike: "Feels like at kickoff",
    airTemp: (t) => `Air ${t}° · heat-index over the match window`,
    home: "home",
    deltaTemp: "Δ temp",
    deltaFeels: "Δ feels",
    bodyClock: "body clock",
    venueSeries: (label, unit) => `${label} (${unit}) · venue (solid) vs home cities (dashed)`,
    venueOnlySeries: (label, unit) => `${label} (${unit}) · venue forecast`,
    knockoutTbd: "Teams decided after the previous round — showing the venue forecast.",
    forecastPending: "Forecast pending",
    forecastPendingNote: "Beyond the 15-day forecast horizon — check back closer to kickoff.",
    forecast: "forecast",
    kickoff: "kickoff",
    localTime: "local",
    deltaWbgt: "Δ WBGT",
    airConLabel: "Air-conditioned stadium",
    airConTip: "This venue has a retractable roof and a climate-controlled bowl. Operators can close the roof and run air conditioning to shield players and fans from heat — expected for hot daytime kickoffs. FIFA also mandates a 3-minute hydration break in each half of every match, regardless of roof or temperature.",
    statInfoTexts: {
      deltaTemp: "Air-temperature difference between home city and venue at kickoff. Orange = venue is hotter than home, blue = cooler.",
      deltaFeels: "Heat-index difference between home and venue. Accounts for humidity — a dry 35°C and a humid 30°C can feel equally bad.",
      deltaWbgt: "WBGT difference. WBGT combines heat, humidity, wind, and solar radiation. FIFA triggered mandatory cooling breaks above 32°C WBGT (2014–2025); FIFPRO recommends action from 28°C.",
      bodyClock: "Approximate time-zone difference between home city and venue (based on longitude). A large jet-lag gap can affect player alertness and recovery.",
      feelsLike: "Heat index at kickoff — combines air temperature and humidity to show how hot it actually feels on the pitch. Above 32°C is considered stressful for athletes.",
      wbgtKickoff: "WBGT (Wet Bulb Globe Temperature) at kickoff. FIFA triggered mandatory cooling breaks above 32°C WBGT (2014–2025); FIFPRO recommends action from 28°C. For 2026, FIFA made breaks mandatory in every match.",
    },
    varLabels: {},
    varInfoTexts: {
      t2m: "Air temperature 2 m above the ground. The raw atmospheric reading — doesn't account for wind or humidity.",
      heat_index: "NOAA heat index: how hot it actually feels, combining temperature and humidity. At 35°C with 80% humidity it can feel like 50°C. Meaningful only above ~27°C.",
      humidex: "Environment Canada's heat-stress scale (Masterton & Richardson, 1979; computed with xclim). 40–45 = great discomfort, avoid exertion; above 45 is dangerous, heat stroke possible.",
      utci: "Universal Thermal Climate Index (computed with xclim) — the most comprehensive outdoor comfort index, combining temperature, humidity, wind, and radiation. Above 26 = moderate, 32 = strong, 38 = very strong heat stress. Widely used in heat-risk research.",
      wbgt: "Wet Bulb Globe Temperature (ISO 7243; natural wet-bulb after Stull 2011) — the gold standard for outdoor sports safety, used in FIFA and IOC heat policy. FIFA triggered mandatory cooling breaks above 32°C WBGT (2014–2025); FIFPRO recommends action from 28°C.",
      d2m: "Dewpoint — the temperature at which air becomes saturated. Above 20°C feels muggy; above 25°C is tropical and very taxing for exercise.",
      wind_speed: "Wind speed 10 m above ground (m/s). Below 2 = calm; 5–10 = noticeable breeze that affects play; above 15 = strong wind.",
    },
    chart: {
      venue: "Venue",
      thresholds: {
        discomfort: "discomfort", dangerous: "dangerous", stopExercise: "stop exercise",
        moderateHeat: "moderate heat", strongHeat: "strong heat", veryStrong: "very strong",
        fifproLimit: "FIFPRO limit", fifaMandatory: "FIFA mandatory",
        breeze: "breeze", windy: "windy", strong: "strong",
        muggy: "muggy", tropical: "tropical",
      },
    },
  },
  de: {
    title: "WM 2026 · Spielklima",
    ecmwf: "ECMWF-Vorhersage",
    cycleLabel: "Vorhersagezeitpunkt",
    demoData: "Demo-Daten",
    errorTitle: "Vorhersagedaten konnten nicht geladen werden",
    errorCmd: "Zuerst ausführen:",
    errorCmdSuffix: "",
    matchCount: (n, when) => `${n} Spiele · ${when}`,
    tempLegend: "Temperatur beim Anstoß",
    close: "Schließen ✕",
    feelsLike: "Gefühlte Temperatur beim Anstoß",
    airTemp: (t) => `Luft ${t}° · Hitzeindex während des Spiels`,
    home: "Heim",
    deltaTemp: "Δ Temp",
    deltaFeels: "Δ Gefühlt",
    bodyClock: "Jetlag",
    venueSeries: (label, unit) => `${label} (${unit}) · Spielort (durchgehend) vs. Heimstädte (gestrichelt)`,
    venueOnlySeries: (label, unit) => `${label} (${unit}) · Vorhersage für den Spielort`,
    knockoutTbd: "Teams stehen nach der vorherigen Runde fest — gezeigt wird die Vorhersage für den Spielort.",
    forecastPending: "Vorhersage ausstehend",
    forecastPendingNote: "Außerhalb des 15-Tage-Vorhersagehorizonts — schau näher am Anstoß noch einmal vorbei.",
    forecast: "Vorhersage",
    kickoff: "Anstoß",
    localTime: "lokal",
    deltaWbgt: "Δ WBGT",
    airConLabel: "Klimatisiertes Stadion",
    airConTip: "Dieser Spielort hat ein schließbares Dach und einen klimatisierten Innenraum. Das Dach kann geschlossen und die Klimaanlage betrieben werden, um Spieler und Fans vor Hitze zu schützen — bei heißen Anstößen am Tag zu erwarten. Die FIFA schreibt zudem in jeder Halbzeit jedes Spiels eine 3-minütige Trinkpause vor, unabhängig von Dach oder Temperatur.",
    statInfoTexts: {
      deltaTemp: "Temperaturdifferenz zwischen Heimatstadt und Spielort beim Anstoß. Orange = Spielort heißer als zu Hause, blau = kühler.",
      deltaFeels: "Hitzeindex-Differenz zwischen Heimatstadt und Spielort. Berücksichtigt Luftfeuchtigkeit – trockene 35°C und schwüle 30°C können sich gleich schlimm anfühlen.",
      deltaWbgt: "WBGT-Differenz. WBGT kombiniert Hitze, Luftfeuchtigkeit, Wind und Sonneneinstrahlung. Die FIFA löste Pflicht-Trinkpausen über 32°C WBGT aus (2014–2025); FIFPRO empfiehlt Maßnahmen ab 28°C.",
      bodyClock: "Ungefähre Zeitzonendifferenz zwischen Heimatstadt und Spielort (längenbasiert). Ein großer Jetlag kann die Aufmerksamkeit und Erholung der Spieler beeinflussen.",
      feelsLike: "Hitzeindex beim Anstoß – kombiniert Lufttemperatur und Luftfeuchtigkeit. Über 32°C gilt als belastend für Sportler.",
      wbgtKickoff: "WBGT (Wet Bulb Globe Temperature) beim Anstoß. Die FIFA löste Pflicht-Trinkpausen über 32°C WBGT aus (2014–2025); FIFPRO empfiehlt Maßnahmen ab 28°C. Für 2026 macht die FIFA Pausen in jedem Spiel zur Pflicht.",
    },
    varLabels: {
      t2m: "Temperatur",
      heat_index: "Gefühlte Temperatur",
      d2m: "Taupunkt",
    },
    varInfoTexts: {
      t2m: "Lufttemperatur 2 m über dem Boden. Der reine atmosphärische Messwert – ohne Wind- und Feuchtigkeitseinfluss.",
      heat_index: "NOAA-Hitzeindex: wie heiß es sich wirklich anfühlt, kombiniert Temperatur und Luftfeuchtigkeit. Bei 35°C und 80% Luftfeuchtigkeit kann es sich wie 50°C anfühlen.",
      humidex: "Hitzestress-Skala von Environment Canada (Masterton & Richardson, 1979; berechnet mit xclim). 40–45 = große Unannehmlichkeit, Anstrengung vermeiden; über 45 gefährlich, Hitzschlag möglich.",
      utci: "Universal Thermal Climate Index (berechnet mit xclim) – das umfassendste Außenkomfort-Modell, kombiniert Temperatur, Luftfeuchtigkeit, Wind und Strahlung. Über 26 = mäßiger, 32 = starker, 38 = sehr starker Hitzestress. Weit verbreitet in der Hitzerisiko-Forschung.",
      wbgt: "Wet Bulb Globe Temperature (ISO 7243; Feuchtkugel nach Stull 2011) – der Goldstandard für Outdoor-Sportsicherheit, genutzt in FIFA- und IOC-Hitzerichtlinien. Die FIFA löste Pflicht-Trinkpausen über 32°C WBGT aus (2014–2025); FIFPRO empfiehlt Maßnahmen ab 28°C.",
      d2m: "Taupunkt – Temperatur, bei der die Luft gesättigt wird. Über 20°C fühlt es sich schwül an; über 25°C ist es tropisch und sehr belastend.",
      wind_speed: "Windgeschwindigkeit 10 m über dem Boden (m/s). Unter 2 = ruhig; 5–10 = spürbarer Wind; über 15 = starker Wind.",
    },
    chart: {
      venue: "Spielort",
      thresholds: {
        discomfort: "Unbehagen", dangerous: "gefährlich", stopExercise: "Sport stoppen",
        moderateHeat: "mäßige Hitze", strongHeat: "starke Hitze", veryStrong: "sehr stark",
        fifproLimit: "FIFPRO-Grenze", fifaMandatory: "FIFA-Pflicht",
        breeze: "Brise", windy: "windig", strong: "stark",
        muggy: "schwül", tropical: "tropisch",
      },
    },
  },
};
