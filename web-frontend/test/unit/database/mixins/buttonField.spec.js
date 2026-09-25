import {
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  test,
  vi,
} from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import buttonField from '@baserow/modules/database/mixins/buttonField'

function context({ executeResults, posthog }) {
  const execute = vi.fn()
  executeResults.forEach((result) => execute.mockResolvedValueOnce(result))
  return {
    field: { id: 7 },
    allFieldsInTable: [{ id: 1 }],
    $registry: { get: () => ({ execute }) },
    $posthog: posthog,
    resultsBefore: buttonField.methods.resultsBefore,
    execute,
  }
}

const actions = [
  { id: 1, type: 'open_url', position: 1 },
  { id: 2, type: 'open_url', position: 2 },
]

describe('buttonField runClientActions', () => {
  test('captures whether each client action ran', async () => {
    const posthog = { capture: vi.fn() }
    const ctx = context({ executeResults: [undefined, false], posthog })

    await buttonField.methods.runClientActions.call(ctx, actions, {})

    expect(posthog.capture.mock.calls).toEqual([
      [
        'button_field_client_action',
        { field_id: 7, workflow_action_type: 'open_url', ran: true },
      ],
      [
        'button_field_client_action',
        { field_id: 7, workflow_action_type: 'open_url', ran: false },
      ],
    ])
  })

  test('runs the actions when PostHog is not configured', async () => {
    const ctx = context({ executeResults: [true, true], posthog: undefined })

    await buttonField.methods.runClientActions.call(ctx, actions, {})

    expect(ctx.execute).toHaveBeenCalledTimes(2)
  })

  test('a failing capture does not stop the next action', async () => {
    const posthog = {
      capture: vi.fn(() => {
        throw new Error('blocked')
      }),
    }
    const ctx = context({ executeResults: [true, true], posthog })

    await buttonField.methods.runClientActions.call(ctx, actions, {})

    expect(ctx.execute).toHaveBeenCalledTimes(2)
  })
})

describe('buttonField new tab actions', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  beforeEach(() => {
    // happy-dom would try to navigate the test document.
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
    testApp.afterEach()
  })

  function fakeTab() {
    return {
      opener: 'page',
      closed: false,
      document: document.implementation.createHTMLDocument(''),
      close: vi.fn(),
    }
  }

  /** The link the tab was sent to, if any. */
  const followedLink = (tab) => tab.document.querySelector('a')

  /**
   * Clicks through the real mixin and the real `open_url` action. The
   * dispatch stays pending until `respond` or `fail` is called, like the
   * request a click waits for.
   */
  function click(field, clientActions) {
    let respond, fail
    const post = vi.fn(
      () =>
        new Promise((resolve, reject) => {
          respond = () => resolve({ data: { client_actions: clientActions } })
          fail = () => reject(new Error('offline'))
        })
    )
    const app = testApp._app
    const ctx = {
      ...buttonField.methods,
      field: { id: 7, ...field },
      row: { id: 1 },
      allFieldsInTable: [{ id: 1, type: 'text', name: 'Name' }],
      dispatching: false,
      dispatchKey: '7:1',
      $client: { post },
      $registry: app.$registry,
      $store: app.$store,
      $t: (key) => key,
    }
    const done = buttonField.methods.dispatchWorkflowActions.call(ctx)
    return { done, respond: () => respond(), fail: () => fail() }
  }

  const openUrl = (target, formula = "'https://example.com'") => ({
    id: 1,
    type: 'open_url',
    position: 1,
    target,
    url: { formula },
  })

  test('the tab opens before the dispatch returns, then goes to the url', async () => {
    const tab = fakeTab()
    const open = vi.spyOn(window, 'open').mockReturnValue(tab)

    const { done, respond } = click({ opens_new_tab: true }, [openUrl('blank')])

    // Still inside the click: Safari blocks a tab opened after the await.
    expect(open).toHaveBeenCalledTimes(1)
    expect(open).toHaveBeenCalledWith('', '_blank')
    expect(tab.opener).toBeNull()
    expect(followedLink(tab)).toBeNull()

    respond()
    await done

    expect(open).toHaveBeenCalledTimes(1)
    const link = followedLink(tab)
    expect(link.href).toBe('https://example.com/')
    expect(link.rel).toBe('noreferrer')
    expect(link.click).toHaveBeenCalled()
    expect(tab.close).not.toHaveBeenCalled()
  })

  test('a failed dispatch closes the tab', async () => {
    const tab = fakeTab()
    vi.spyOn(window, 'open').mockReturnValue(tab)
    vi.spyOn(testApp._app.$store, 'dispatch')

    const { done, fail } = click({ opens_new_tab: true }, [openUrl('blank')])
    fail()
    await done

    expect(followedLink(tab)).toBeNull()
    expect(tab.close).toHaveBeenCalled()
  })

  test('a url that does not resolve closes the tab', async () => {
    const tab = fakeTab()
    vi.spyOn(window, 'open').mockReturnValue(tab)
    vi.spyOn(testApp._app.$store, 'dispatch')

    const { done, respond } = click({ opens_new_tab: true }, [
      openUrl('blank', "'javascript:alert(1)'"),
    ])
    respond()
    await done

    expect(followedLink(tab)).toBeNull()
    expect(tab.close).toHaveBeenCalled()
  })

  test('a tab closed during the dispatch falls back to opening the url', async () => {
    const tab = fakeTab()
    const open = vi.spyOn(window, 'open').mockReturnValue(tab)

    const { done, respond } = click({ opens_new_tab: true }, [openUrl('blank')])
    tab.closed = true
    respond()
    await done

    expect(followedLink(tab)).toBeNull()
    expect(open).toHaveBeenLastCalledWith(
      'https://example.com',
      '_blank',
      'noopener,noreferrer'
    )
  })

  test.each(['mailto:ada@example.com', 'tel:+441234567890'])(
    'a new tab %s url goes to another app and leaves no empty tab',
    async (url) => {
      const tab = fakeTab()
      const open = vi.spyOn(window, 'open').mockReturnValue(tab)
      const originalLocation = window.location
      Object.defineProperty(window, 'location', {
        value: { href: 'http://localhost/database/1/table/1' },
        writable: true,
        configurable: true,
      })

      try {
        const { done, respond } = click({ opens_new_tab: true }, [
          openUrl('blank', `'${url}'`),
        ])
        respond()
        await done

        expect(followedLink(tab)).toBeNull()
        expect(tab.close).toHaveBeenCalled()
        expect(open).toHaveBeenCalledTimes(1)
        expect(window.location.href).toBe(url)
      } finally {
        Object.defineProperty(window, 'location', {
          value: originalLocation,
          writable: true,
          configurable: true,
        })
      }
    }
  )

  test('a button without a new tab action opens no tab', async () => {
    const open = vi.spyOn(window, 'open')

    const { done, respond } = click({ opens_new_tab: false }, [])
    respond()
    await done

    expect(open).not.toHaveBeenCalled()
  })

  test('a blocked placeholder falls back to opening the url', async () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)

    const { done, respond } = click({ opens_new_tab: true }, [openUrl('blank')])
    respond()
    await done

    expect(open).toHaveBeenLastCalledWith(
      'https://example.com',
      '_blank',
      'noopener,noreferrer'
    )
  })
})
