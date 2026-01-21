import { beforeEach, vi, expect } from 'vitest'

const tMock = (key: string, data: any) =>
  data?.count !== undefined ? `${key} - ${data.count}` : key

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
        i18n.global.t = tMock
        i18n.global.getBrowserLocale = () => 'en'
      }

      return i18n
    },

    // Also cover direct composable usage in code:
    useI18n: (...args: any[]) => {
      const composer = actual.useI18n?.(...args)
      return {
        ...composer,
        t: tMock,
        getBrowserLocale: () => 'en',
      }
    },
  }
})

// deterministic UUIDs (nice when multiple UUIDs happen in one render)
const uuidMockState = vi.hoisted(() => {
  let i = 1

  return {
    next() {
      // pad to 12 digits to keep UUID shape stable
      const suffix = String(i++).padStart(12, '0')
      return `00000000-0000-0000-0000-${suffix}`
    },
    reset() {
      i = 1
    },
  }
})

vi.mock('@baserow/modules/core/utils/string', async () => {
  const actual = await vi.importActual<any>(
    '@baserow/modules/core/utils/string'
  )

  return {
    ...actual,
    uuid: vi.fn(() => uuidMockState.next()),
  }
})

beforeEach(() => {
  uuidMockState.reset()
})

// Mock Nuxt components
//config.stubs.nuxt = { template: '<div />' }
//config.stubs['nuxt-link'] = { template: '<a><slot /></a>' }
//config.stubs['no-ssr'] = { template: '<span><slot /></span>' }

function fail(message = '') {
  let failMessage = ''
  failMessage += '\n'
  failMessage += 'FAIL FUNCTION TRIGGERED\n'
  failMessage += 'The fail function has been triggered'
  failMessage += message ? ' with message:' : ''

  expect(message).toEqual(failMessage)
}
global.fail = fail

/*process.on('unhandledRejection', (err) => {
  fail(err)
})*/

// We can't test socket anyway
global.WebSocket = class {
  close() {}
  send() {}
}
