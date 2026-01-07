import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Make template + Options API `this.$t()` return the key
/*config.global.mocks = {
  ...(config.global.mocks ?? {}),
  $t: (key: string) => key,
  $i18n: {
    t: vi.fn((key: string) => key),
    getBrowserLocale: () => 'en',
  },
}*/
/*
vi.mock('#app', async (importOriginal) => {
  const actual = await importOriginal<any>()

  return {
    ...actual, // <-- keeps defineNuxtPlugin and everything else
    useNuxtApp: () => ({
      // Provide the bits your components expect from useNuxtApp()
      $i18n: {
        t: vi.fn((key: string) => key),
        getBrowserLocale: () => 'en',
      },
    }),
  }
})

// Keep vue-i18n real exports (createI18n, etc.) but override useI18n().t
vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<any>()
  return {
    ...actual,
    useI18n: (...args: any[]) => {
      // if something needs the real composer, you can still get it:
      const composer = actual.useI18n?.(...args) ?? {}
      return {
        ...composer,
        t: (key: string) => key,
      }
    },
  }
})
*/

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
