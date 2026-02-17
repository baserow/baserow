import moment from '@baserow/modules/core/moment'

export default defineNuxtPlugin({
  name: 'i18n',
  async setup(nuxtApp) {
    const { $i18n } = nuxtApp

    moment.locale($i18n.locale.value)

    $i18n.onLanguageSwitched = (oldLocale, newLocale) => {
      moment.locale(newLocale)
    }

    if ($i18n.locale.value !== 'en') {
      try {
        $i18n.fallbackLocale.value = 'en'
        await $i18n.loadLocaleMessages('en')
      } catch (error) {
        console.warn('Failed to load fallback locale messages:', error)
      }
    }
  },
})
