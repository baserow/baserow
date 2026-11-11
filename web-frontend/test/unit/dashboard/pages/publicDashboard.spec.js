import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import { setToken, unsetToken } from '@baserow/modules/core/utils/auth'
import { PUBLIC_DASHBOARD_AUTHORIZATION_HEADER } from '@baserow/modules/dashboard/services/publicDashboard'
import PublicDashboardPage from '@baserow/modules/dashboard/pages/publicDashboard'

describe('PublicDashboard page', () => {
  let testApp = null
  let nuxtApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    nuxtApp = testApp.getApp()
    store = testApp.getStore()
    testApp.mockServer.fakeSettings()
  })

  afterEach(() => testApp.afterEach())

  function publicDashboardInfo() {
    return {
      dashboard: {
        id: 1,
        name: 'Conversion compass',
        description: 'Tracking conversion rates at every stage.',
        show_logo: true,
      },
      widgets: [],
      data_sources: [],
    }
  }

  function findInfoRequest(slug) {
    return testApp.mock.history.get.find(
      (request) => request.url === `/dashboard/public/${slug}/`
    )
  }

  test('shows a shared dashboard without a password', async () => {
    const slug = 'open-slug'
    testApp.mock
      .onGet(`/dashboard/public/${slug}/`)
      .reply(200, publicDashboardInfo())

    const page = await testApp.mount(PublicDashboardPage, {
      route: `/public/dashboard/${slug}`,
    })

    expect(page.text()).toContain('Conversion compass')
    expect(store.getters['dashboardApplication/getPublicSlug']).toBe(slug)
    expect(store.getters['dashboardApplication/getPublicAuthToken']).toBe(null)
    expect(
      findInfoRequest(slug).headers[PUBLIC_DASHBOARD_AUTHORIZATION_HEADER]
    ).toBeUndefined()
  })

  test('sends the token remembered for the slug', async () => {
    const slug = 'remembered-slug'
    await setToken(nuxtApp, 'cookie-token', slug)
    testApp.mock
      .onGet(`/dashboard/public/${slug}/`)
      .reply(200, publicDashboardInfo())

    try {
      const page = await testApp.mount(PublicDashboardPage, {
        route: `/public/dashboard/${slug}`,
      })

      expect(page.text()).toContain('Conversion compass')
      expect(
        findInfoRequest(slug).headers[PUBLIC_DASHBOARD_AUTHORIZATION_HEADER]
      ).toBe('JWT cookie-token')
      expect(store.getters['dashboardApplication/getPublicAuthToken']).toBe(
        'cookie-token'
      )
    } finally {
      await unsetToken(nuxtApp, slug)
    }
  })

  test('sends visitors of a password protected dashboard to the password page', async () => {
    const slug = 'protected-slug'
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet(`/dashboard/public/${slug}/`).reply(401, {
      error: 'ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD',
      detail: 'A valid password is required.',
    })

    const page = await testApp.mount(PublicDashboardPage, {
      route: `/public/dashboard/${slug}`,
    })
    await flushPromises()

    const current = nuxtApp.$router.currentRoute.value
    expect(current.name).toBe('dashboard-public-auth')
    expect(current.params.slug).toBe(slug)
    expect(current.query.original).toBe(`/public/dashboard/${slug}`)
    expect(page.text()).not.toContain('Conversion compass')
    expect(store.getters['dashboardApplication/isPublic']).toBe(false)
  })
})
