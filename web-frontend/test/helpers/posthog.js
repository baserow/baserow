import { vi } from 'vitest'

const posthog = { capture: vi.fn() }

export const providePosthog = (nuxtApp) => {
  if (!('$posthog' in nuxtApp)) {
    nuxtApp.provide('posthog', posthog)
  }
  posthog.capture.mockClear()
  return posthog
}
