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
