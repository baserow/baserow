import moment from '@baserow/modules/core/moment'

export default defineNuxtPlugin({
  name: 'i18n',
  async setup(nuxtApp) {
    const { $i18n } = nuxtApp

    moment.locale($i18n.locale.value)

    const loadFallbackIfNeeded = async (locale) => {
      if (locale !== 'en') {
        try {
          $i18n.fallbackLocale.value = 'en'
          await $i18n.loadLocaleMessages('en')
        } catch (error) {
          console.warn('Failed to load fallback locale messages:', error)
        }
      }
    }

    // Use watch to react to client side locale switch
    watch($i18n.locale, async (newLocale, oldLocale) => {
      moment.locale(newLocale)
      await loadFallbackIfNeeded(newLocale)
    })

    await loadFallbackIfNeeded($i18n.locale.value)
  },
})
