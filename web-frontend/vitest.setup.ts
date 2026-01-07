import { vi } from 'vitest'

// Mock i18n to return key instead of actual translation
vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<any>()

  return {
    ...actual,

    // This is what @nuxtjs/i18n uses internally to create the i18n instance.
    createI18n: (options: any = {}) => {
      const i18n = actual.createI18n({
        ...options,

        // Disable noisy warnings:
        missingWarn: false,
        fallbackWarn: false,

        // Make missing keys return the key:
        missing: (_locale: string, key: string) => key,
      })

      // Make sure *any* call to global.t returns the key (templates use this)
      if (i18n?.global) {
        i18n.global.t = (key: string) => key
        i18n.global.getBrowserLocale = () => 'en'
      }

      return i18n
    },

    // Also cover direct composable usage in code:
    useI18n: (...args: any[]) => {
      const composer = actual.useI18n?.(...args)
      return {
        ...composer,
        t: (key: string) => key,
        getBrowserLocale: () => 'en',
      }
    },
  }
})
