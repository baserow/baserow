import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// Maps Baserow i18n locale codes to vuejs3-datepicker language keys.
// The datepicker uses non-standard keys for some languages (e.g. 'kr' for Korean, 'vn' for Vietnamese).
// Source: https://github.com/shubhadip/vuejs3-datepicker/blob/master/src/components/datepicker/locale/index.ts
const LOCALE_TO_DATEPICKER = {
  ar: 'ar',
  af: 'af',
  bg: 'bg',
  cs: 'cs',
  de: 'de',
  en: 'en',
  es: 'es',
  fr: 'fr',
  hi: 'hi',
  id: 'id',
  it: 'it',
  ja: 'ja',
  ko: 'kr', // datepicker uses 'kr' for Korean
  nl: 'nl',
  pl: 'pl',
  pt: 'pt',
  pt_BR: 'pt', // no Brazilian variant, falls back to Portuguese
  pt_PT: 'pt', // no Portugal variant, falls back to Portuguese
  ru: 'ru',
  tr: 'tr',
  vi: 'vn', // datepicker uses 'vn' for Vietnamese
  zh_TW: 'zh_TW',
}

export function useDatePickerLanguage() {
  const { locale } = useI18n()
  const datePickerLanguage = computed(
    () => LOCALE_TO_DATEPICKER[locale.value] ?? 'en'
  )
  return { datePickerLanguage }
}
