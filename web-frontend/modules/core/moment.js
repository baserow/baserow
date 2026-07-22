// Moment should always be imported from here. This will enforce that the timezone
// is always included. There were some problems when Baserow is installed as a
// dependency and then moment-timezone does not work. Still will resolve that issue.
import moment from 'moment-timezone'

const localeLoaders = {
  fr: () => import('moment/dist/locale/fr'),
  nl: () => import('moment/dist/locale/nl'),
  de: () => import('moment/dist/locale/de'),
  es: () => import('moment/dist/locale/es'),
  it: () => import('moment/dist/locale/it'),
  pl: () => import('moment/dist/locale/pl'),
  ko: () => import('moment/dist/locale/ko'),
  uk: () => import('moment/dist/locale/uk'),
}

export async function loadMomentLocale(locale) {
  await localeLoaders[locale]?.()
}

export default moment
