import moment from '@baserow/modules/core/moment'

export default defineNuxtPlugin({
  name: 'i18n',
  async setup(nuxtApp) {
    const { $i18n } = nuxtApp
    // Resolved lazily, because the first call creates the indicator with its
    // options, and those must come from the `NuxtLoadingIndicator` in `app.vue`.
    const getLoadingIndicator = () =>
      nuxtApp.runWithContext(() => useLoadingIndicator())

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
    watch($i18n.locale, (newLocale) => {
      moment.locale(newLocale)
    })

    // Switching the language downloads the messages of the new locale, which can
    // take a while on a slow connection, so the progress bar is shown until
    // everything of the new locale has been loaded.
    nuxtApp.hook('i18n:beforeLocaleSwitch', () => {
      // `initialSetup` can't be used to skip the first page load, because it's
      // never reset with the `no_prefix` strategy.
      if (import.meta.client && !nuxtApp.isHydrating) {
        getLoadingIndicator().start()
      }
    })
    nuxtApp.hook('i18n:localeSwitched', async ({ newLocale }) => {
      try {
        await loadFallbackIfNeeded(newLocale)
      } finally {
        if (import.meta.client) {
          getLoadingIndicator().finish()
        }
      }
    })

    await loadFallbackIfNeeded($i18n.locale.value)
  },
})
