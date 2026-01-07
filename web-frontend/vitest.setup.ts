import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Make template + Options API `this.$t()` return the key
config.global.mocks = {
  ...(config.global.mocks ?? {}),
  $t: (key: string) => key,
}

vi.mock('#app', async (importOriginal) => {
  const actual = await importOriginal<any>()

  return {
    ...actual, // <-- keeps defineNuxtPlugin and everything else
    useNuxtApp: () => ({
      // Provide the bits your components expect from useNuxtApp()
      $i18n: {
        t: vi.fn((key: string) => key),
      },
    }),
  }
})
