/*import moment from '@baserow/modules/core/moment'

export default function ({ app }) {
  // Set moment locale on load
  moment.locale(app.i18n.locale)

  app.i18n.onLanguageSwitched = (oldLocale, newLocale) => {
    // Update moment locale on language switch
    moment.locale(newLocale)
  }
}
*/

import moment from '@baserow/modules/core/moment'

export default defineNuxtPlugin({
  name: 'i18n',
  setup(nuxtApp) {
    const { $i18n } = nuxtApp

    moment.locale($i18n.locale.value)

    $i18n.onLanguageSwitched = (oldLocale, newLocale) => {
      moment.locale(newLocale)
    }
  },
})
