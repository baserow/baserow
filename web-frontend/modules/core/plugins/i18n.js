import moment, { loadMomentLocale } from '@baserow/modules/core/moment'
import { watch } from 'vue'
import { defineNuxtPlugin } from '#imports'

export default defineNuxtPlugin({
  name: 'i18n',
  async setup(nuxtApp) {
    const { $i18n } = nuxtApp

    const updateMomentLocale = async (locale) => {
      try {
        await loadMomentLocale(locale)
      } catch (error) {
        console.warn('Failed to load Moment locale:', error)
      }
      // Locale modules change Moment's global locale when they register. An
      // older import can finish after a newer switch, so always restore the
      // currently selected language instead of the import's original language.
      moment.locale($i18n.locale.value)
    }

    await updateMomentLocale($i18n.locale.value)

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
    watch($i18n.locale, async (newLocale) => {
      await updateMomentLocale(newLocale)
      await loadFallbackIfNeeded($i18n.locale.value)
    })

    await loadFallbackIfNeeded($i18n.locale.value)
  },
})
