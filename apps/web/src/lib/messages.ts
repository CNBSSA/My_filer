import en from "../../messages/en.json";
import ha from "../../messages/ha.json";
import yo from "../../messages/yo.json";
import ig from "../../messages/ig.json";
import pcm from "../../messages/pcm.json";

export type LanguageCode = "en" | "ha" | "yo" | "ig" | "pcm";

export const LANGUAGE_CODES: LanguageCode[] = ["en", "ha", "yo", "ig", "pcm"];

export const LANGUAGE_LABELS: Record<LanguageCode, string> = {
  en: "English",
  ha: "Hausa",
  yo: "Yorùbá",
  ig: "Igbo",
  pcm: "Naijá",
};

export type Messages = typeof en;

const CATALOG: Record<LanguageCode, Messages> = {
  en: en as Messages,
  ha: ha as Messages,
  yo: yo as Messages,
  ig: ig as Messages,
  pcm: pcm as Messages,
};

export function getMessages(code: string | null | undefined): Messages {
  const normalized = (code ?? "en").toLowerCase() as LanguageCode;
  return CATALOG[normalized] ?? CATALOG.en;
}
