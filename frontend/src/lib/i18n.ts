import i18n from "i18next"
import LanguageDetector from "i18next-browser-languagedetector"
import { initReactI18next } from "react-i18next"

import { ar } from "@/i18n/locales/ar"
import { de } from "@/i18n/locales/de"
import { en } from "@/i18n/locales/en"
import { esES } from "@/i18n/locales/es-ES"
import { fa } from "@/i18n/locales/fa"
import { fr } from "@/i18n/locales/fr"
import { hu } from "@/i18n/locales/hu"
import { ja } from "@/i18n/locales/ja"
import { ko } from "@/i18n/locales/ko"
import { pl } from "@/i18n/locales/pl"
import { ptBR } from "@/i18n/locales/pt-BR"
import { ru } from "@/i18n/locales/ru"
import { tr } from "@/i18n/locales/tr"
import { uk } from "@/i18n/locales/uk"
import { zhCN } from "@/i18n/locales/zh-CN"
import { zhTW } from "@/i18n/locales/zh-TW"
import { legacyAuroraDesignResources } from "@/i18n/aurora-legacy"
import { LOCALES, type Dict, type Locale } from "@/i18n/types"

type Namespace = "common" | "chat" | "construct"
type NamespaceResources = Record<Namespace, Record<string, string>>

export const supportedLanguages = LOCALES

const dictionaries: Record<Locale, Dict> = {
  en,
  de,
  "zh-CN": zhCN,
  "zh-TW": zhTW,
  "pt-BR": ptBR,
  "es-ES": esES,
  ru,
  fa,
  ar,
  ja,
  ko,
  pl,
  hu,
  fr,
  uk,
  tr,
}

export function normalizeLanguage(language?: string | null): Locale {
  if (!language) return "zh-CN"

  const lower = language.toLowerCase()
  if (lower === "zh" || lower === "zh-cn" || lower === "zh-hans") return "zh-CN"
  if (lower === "zh-tw" || lower === "zh-hant") return "zh-TW"
  if (lower === "pt-br") return "pt-BR"
  if (lower === "es-es") return "es-ES"

  const exact = LOCALES.find((locale) => locale === language)
  if (exact) return exact

  const byLanguage = LOCALES.find((locale) => locale.toLowerCase().split("-")[0] === lower.split("-")[0])
  return byLanguage ?? "zh-CN"
}

function normalizeInterpolation(value: string): string {
  return value.replace(/(?<!\{)\{([A-Za-z]\w*)\}(?!\})/g, "{{$1}}")
}

function normalizeDict(dict: Dict): Record<string, string> {
  return Object.fromEntries(
    Object.entries(dict).map(([key, value]) => [key, normalizeInterpolation(value)]),
  )
}

function makeNamespaces(locale: Locale, dict: Dict): NamespaceResources {
  const base = normalizeDict(dict)
  const legacy = locale === "zh-CN" || locale === "en" ? legacyAuroraDesignResources[locale] : undefined

  return {
    common: { ...base, ...legacy?.common },
    chat: { ...base, ...legacy?.chat },
    construct: { ...base, ...legacy?.construct },
  }
}

export const resources = Object.fromEntries(
  LOCALES.map((locale) => [locale, makeNamespaces(locale, dictionaries[locale])]),
) as Record<Locale, NamespaceResources>

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    supportedLngs: LOCALES,
    fallbackLng: "zh-CN",
    defaultNS: "common",
    ns: ["common", "chat", "construct"],
    keySeparator: false,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      convertDetectedLanguage: normalizeLanguage,
    },
  })

export default i18n
