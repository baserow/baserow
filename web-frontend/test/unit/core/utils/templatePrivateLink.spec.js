import { afterEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import {
  addPrivateLinkTokenHeader,
  addReplayOutsidePrivateLinks,
  redactPrivateLinkTokens,
} from '@baserow/modules/core/utils/templatePrivateLink'

const TOKEN = 'a'.repeat(64)

describe('addPrivateLinkTokenHeader', () => {
  test.each([
    ['template-private-link', TOKEN, TOKEN],
    ['template', TOKEN, undefined],
    ['template-private-link', TOKEN.toUpperCase(), undefined],
  ])('on %s with %s sends %s', (name, token, expected) => {
    const nuxtApp = {
      $router: { currentRoute: { value: { name, params: { token } } } },
    }

    const config = addPrivateLinkTokenHeader(nuxtApp)({ headers: {} })

    expect(config.headers['Baserow-Template-Authorization']).toBe(expected)
  })

  test('keeps the token of a link opened before', () => {
    const nuxtApp = {
      $router: {
        currentRoute: {
          value: { name: 'template-private-link', params: { token: TOKEN } },
        },
      },
    }
    const before = 'b'.repeat(64)

    const config = addPrivateLinkTokenHeader(nuxtApp)({
      headers: { 'Baserow-Template-Authorization': before },
    })

    expect(config.headers['Baserow-Template-Authorization']).toBe(before)
  })
})

describe('redactPrivateLinkTokens', () => {
  test('replaces the token in the URLs of an event', () => {
    const link = `https://baserow.io/template/crm/private-link/${TOKEN}`
    const login = `https://baserow.io/login?original=%2Ftemplate%2Fcrm%2Fprivate-link%2F${TOKEN}`

    const event = redactPrivateLinkTokens({
      event: '$identify',
      properties: {
        $current_url: link,
        $pathname: '/dashboard',
        list: [login],
      },
      $set_once: { $initial_current_url: login },
    })

    expect(event.properties).toEqual({
      $current_url: 'https://baserow.io/template/crm/private-link/[redacted]',
      $pathname: '/dashboard',
      list: [
        'https://baserow.io/login?original=%2Ftemplate%2Fcrm%2Fprivate-link%2F[redacted]',
      ],
    })
    expect(event.$set_once.$initial_current_url).not.toContain(TOKEN)
  })

  test('replaces the token anywhere in an error report', () => {
    const timestamp = new Date()

    const event = redactPrivateLinkTokens({
      request: { url: `https://baserow.io/template/crm/private-link/${TOKEN}` },
      breadcrumbs: [{ data: { to: `/template/crm/private-link/${TOKEN}` } }],
      timestamp,
      level: null,
    })

    expect(JSON.stringify(event)).not.toContain(TOKEN)
    expect(event.timestamp).toBe(timestamp)
  })

  const ENCODED = '%61'.repeat(64)

  test.each([
    [`https://baserow.io/template/crm/private-link/${ENCODED}`],
    [
      `https://baserow.io/login?original=%2Ftemplate%2Fcrm%2Fprivate-link%2F${'%2561'.repeat(64)}`,
    ],
    [
      `https://baserow.io/?next=%252Flogin%253Foriginal%253D%25252Fprivate-link%25252F${'%252561'.repeat(64)}`,
    ],
  ])('replaces an encoded token in %s', (url) => {
    const event = redactPrivateLinkTokens({ request: { url } })

    expect(event.request.url).toMatch(/private-link(\/|%(25)*2F)\[redacted\]$/)
  })
})

describe('addReplayOutsidePrivateLinks', () => {
  const LINK = `/template/crm/private-link/${TOKEN}`

  afterEach(() => {
    window.history.replaceState({}, '', '/')
  })

  const addReplay = async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:path(.*)*', component: { render: () => null } }],
    })
    const replay = { stop: vi.fn() }
    const addIntegration = vi.fn()
    await addReplayOutsidePrivateLinks({
      router,
      loadReplayIntegration: async () => () => replay,
      addIntegration,
      replayOptions: {},
    })
    return { router, replay, addIntegration }
  }

  test.each([LINK, `/login?original=${encodeURIComponent(LINK)}`])(
    'records nothing on %s',
    async (url) => {
      window.history.replaceState({}, '', url)

      const { addIntegration } = await addReplay()

      expect(addIntegration).not.toHaveBeenCalled()
    }
  )

  test('records nothing when a private link opens while the replay loads', async () => {
    window.history.replaceState({}, '', '/dashboard')
    let loadPage
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/template/:slug/private-link/:token',
          component: () => new Promise((resolve) => (loadPage = resolve)),
        },
        { path: '/:path(.*)*', component: { render: () => null } },
      ],
    })
    await router.push('/dashboard')
    let loadReplay
    const replay = { stop: vi.fn() }
    const addIntegration = vi.fn()
    const added = addReplayOutsidePrivateLinks({
      router,
      loadReplayIntegration: () =>
        new Promise((resolve) => (loadReplay = resolve)),
      addIntegration,
      replayOptions: {},
    })

    const opened = router.push(LINK)
    await flushPromises()
    loadReplay(() => replay)
    await added
    loadPage({ render: () => null })
    await opened

    expect(addIntegration).not.toHaveBeenCalled()
  })

  test('stops the replay before a private link is opened', async () => {
    window.history.replaceState({}, '', '/dashboard')
    const { router, replay, addIntegration } = await addReplay()

    expect(addIntegration).toHaveBeenCalledWith(replay)

    await router.push('/template/crm')
    expect(replay.stop).not.toHaveBeenCalled()

    await router.push({ path: '/login', query: { original: LINK } })
    await flushPromises()

    expect(replay.stop).toHaveBeenCalledWith({ flush: false })
  })
})
