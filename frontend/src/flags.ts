// Team name -> emoji flag. ISO-3166 alpha-2 turned into regional-indicator pairs,
// with England/Scotland as their subdivision flags.
const ISO: Record<string, string> = {
  Algeria: "DZ", Argentina: "AR", Australia: "AU", Austria: "AT", Belgium: "BE",
  "Bosnia and Herzegovina": "BA", Brazil: "BR", Canada: "CA", "Cape Verde": "CV",
  Colombia: "CO", Croatia: "HR", Curacao: "CW", Czechia: "CZ", "DR Congo": "CD",
  Ecuador: "EC", Egypt: "EG", France: "FR", Germany: "DE", Ghana: "GH", Haiti: "HT",
  Iran: "IR", Iraq: "IQ", "Ivory Coast": "CI", Japan: "JP", Jordan: "JO", Mexico: "MX",
  Morocco: "MA", Netherlands: "NL", "New Zealand": "NZ", Norway: "NO", Panama: "PA",
  Paraguay: "PY", Portugal: "PT", Qatar: "QA", "Saudi Arabia": "SA", Senegal: "SN",
  "South Africa": "ZA", "South Korea": "KR", Spain: "ES", Sweden: "SE",
  Switzerland: "CH", Tunisia: "TN", Turkiye: "TR", USA: "US", Uruguay: "UY",
  Uzbekistan: "UZ",
};

const SPECIAL: Record<string, string> = {
  England: "🏴\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}",
  Scotland: "🏴\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}",
};

export function flag(team: string): string {
  if (SPECIAL[team]) return SPECIAL[team];
  const code = ISO[team];
  if (!code) return "🏳️";
  return String.fromCodePoint(...[...code].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}
