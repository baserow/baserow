import moment from '@baserow/modules/core/moment'

export default function ({ app }, inject) {
  // Set moment locale on load
  moment.locale(app.i18n.locale)

  let dir =
    app.i18n.locales.find((x) => x.code === app.i18n.locale)?.dir || 'ltr'

  app.i18n.onLanguageSwitched = (oldLocale, newLocale) => {
    dir = app.i18n.locales.find((x) => x.code === newLocale)?.dir || 'ltr'
    // Update moment locale on language switch
    moment.locale(newLocale)
  }

  inject('getLangDir', () => dir)
}
