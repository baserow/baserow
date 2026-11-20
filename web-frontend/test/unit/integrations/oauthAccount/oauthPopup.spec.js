import {
  announceOAuthResult,
  openOAuthPopup,
  waitForOAuthResult,
} from '@baserow/modules/core/utils/oauthPopup'

const TYPE = 'baserow-test_oauth-oauth'
const deliver = () => new Promise((resolve) => setTimeout(resolve, 20))
const options = (extra = {}) => ({
  timeoutMs: 1000,
  cancelled: () => new Error('cancelled'),
  timedOut: () => new Error('timed out'),
  ...extra,
})

describe('OAuth popup', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  test('each popup gets a window of its own', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)

    expect(openOAuthPopup(TYPE)).toBeNull()
    openOAuthPopup(TYPE)

    const [first, second] = open.mock.calls.map((call) => call[1])
    expect(first).toMatch(/^baserow-test_oauth-oauth-/)
    expect(first).not.toBe(second)
  })

  test('only the result of its own sign-in is waited for', async () => {
    const result = waitForOAuthResult(TYPE, 'mine', options())

    announceOAuthResult({ type: TYPE, state: 'theirs', error: null })
    announceOAuthResult({ type: 'baserow-other-oauth', state: 'mine' })
    announceOAuthResult({ type: TYPE, state: 'mine', error: null })
    await deliver()

    await expect(result).resolves.toEqual({
      type: TYPE,
      state: 'mine',
      error: null,
    })
  })

  test('messages from another origin are ignored', async () => {
    const result = waitForOAuthResult(TYPE, 'mine', options())

    window.dispatchEvent(
      new MessageEvent('message', {
        origin: 'https://evil.example.com',
        data: { type: TYPE, state: 'mine', integration: { id: 1 } },
      })
    )
    window.dispatchEvent(
      new MessageEvent('message', {
        origin: window.location.origin,
        data: { type: TYPE, state: 'mine', integration: { id: 2 } },
      })
    )

    await expect(result).resolves.toMatchObject({ integration: { id: 2 } })
  })

  test('waiting stops when given up or out of time', async () => {
    const controller = new AbortController()
    const given_up = waitForOAuthResult(
      TYPE,
      'mine',
      options({ signal: controller.signal })
    )
    controller.abort()
    await expect(given_up).rejects.toThrow('cancelled')

    vi.useFakeTimers()
    const late = waitForOAuthResult(TYPE, 'late', options())
    vi.advanceTimersByTime(1001)
    await expect(late).rejects.toThrow('timed out')
  })
})
