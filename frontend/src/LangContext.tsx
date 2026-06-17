import { createContext, useContext, useState } from "react";
import type { Lang } from "./i18n";

const detect = (): Lang =>
  typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("de") ? "de" : "en";

const LangContext = createContext<[Lang, (l: Lang) => void]>(["en", () => {}]);

export const useLang = () => useContext(LangContext);

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>(detect);
  return <LangContext.Provider value={[lang, setLang]}>{children}</LangContext.Provider>;
}
