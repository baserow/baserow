import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'
import { clearError, useError } from '#app'

import { TestApp } from '@baserow/test/helpers/testApp'
import { getToken, unsetToken } from '@baserow/modules/core/utils/auth'
import PublicDashboardAuth from '@baserow/modules/dashboard/pages/publicDashboardAuth'

const SLUG = 'protected-slug'

describe('PublicDashboardAuth page', () => {
  let testApp = null
  let nuxtApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    nuxtApp = testApp.getApp()
    store = testApp.getStore()
  })

  afterEach(async () => {
    // The router is shared by every test in this file, so a spy on it must not
    // keep the calls of the previous test.
    vi.restoreAllMocks()
    await clearError()
    await unsetToken(nuxtApp, SLUG)
    await testApp.afterEach()
  })

  async function mountPage(query = '', { showLogo = true } = {}) {
    testApp.mock
      .onGet(`/dashboard/public/${SLUG}/auth/`)
      .reply(200, { show_logo: showLogo })
    const page = await testApp.mount(PublicDashboardAuth, {
      route: `/public/dashboard/${SLUG}/auth${query}`,
    })
    // The page navigates through the router of the app, nothing has to be
    // rendered for that.
    const push = vi.spyOn(nuxtApp.$router, 'push').mockResolvedValue()
    return { page, push }
  }

  async function submitPassword(page, password) {
    await page.find('input[type="password"]').setValue(password)
    await page.find('form').trigger('submit')
    await flushPromises()
  }

  test('stores the token for the right password and sends the visitor back', async () => {
    testApp.mock
      .onPost(`/dashboard/public/${SLUG}/auth/`, {
        password: 'secret-password',
      })
      .reply(200, { access_token: 'access-token' })

    const { page, push } = await mountPage(
      `?original=/public/dashboard/${SLUG}`
    )
    await submitPassword(page, 'secret-password')

    expect(store.getters['dashboardApplication/getPublicAuthToken']).toBe(
      'access-token'
    )
    expect(await getToken(nuxtApp, SLUG)).toBe('access-token')
    expect(push).toHaveBeenCalledWith(`/public/dashboard/${SLUG}`)
  })

  test('sends the visitor to the dashboard instead of an external URL', async () => {
    testApp.mock
      .onPost(`/dashboard/public/${SLUG}/auth/`, {
        password: 'secret-password',
      })
      .reply(200, { access_token: 'access-token' })

    const { page, push } = await mountPage(
      '?original=https://attacker.example.com/'
    )
    await submitPassword(page, 'secret-password')

    expect(push).toHaveBeenCalledWith({
      name: 'dashboard-public',
      params: { slug: SLUG },
    })
  })

  test('shows an error for a wrong password', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onPost(`/dashboard/public/${SLUG}/auth/`).reply(401, {
      error: 'ERROR_NO_AUTHORIZATION_TO_PUBLIC_DASHBOARD',
      detail: 'A valid password is required.',
    })

    const { page, push } = await mountPage()
    await submitPassword(page, 'wrong-password')

    expect(page.text()).toContain('publicDashboardAuth.incorrectPasswordTitle')
    expect(push).not.toHaveBeenCalled()
    expect(store.getters['dashboardApplication/getPublicAuthToken']).toBe(null)
    expect(await getToken(nuxtApp, SLUG)).toBeFalsy()
  })

  test('shows the Baserow logo by default', async () => {
    const { page } = await mountPage()

    expect(page.find('.public-dashboard-auth__footer').exists()).toBe(true)
  })

  test('hides the Baserow logo when the owner hid it', async () => {
    const { page } = await mountPage('', { showLogo: false })

    expect(page.find('.public-dashboard-auth__footer').exists()).toBe(false)
  })

  test('shows the not found page for an unknown or private dashboard', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet(`/dashboard/public/${SLUG}/auth/`).reply(404, {
      error: 'ERROR_DASHBOARD_DOES_NOT_EXIST',
      detail: 'The requested dashboard does not exist.',
    })

    // The page hands the fatal error to Nuxt, which renders its error page
    // instead of the password page. The error page isn't part of the test, so
    // the mount itself doesn't succeed.
    await testApp
      .mount(PublicDashboardAuth, {
        route: `/public/dashboard/${SLUG}/auth`,
      })
      .catch(() => {})

    const error = useError()
    expect(error.value?.statusCode).toBe(404)
    expect(error.value?.message).toBe('Dashboard not found.')
  })

  test('asks for a password before sending anything', async () => {
    const { page, push } = await mountPage()
    await page.find('form').trigger('submit')
    await flushPromises()

    expect(testApp.mock.history.post).toHaveLength(0)
    expect(page.text()).toContain('error.requiredField')
    expect(push).not.toHaveBeenCalled()
  })
})
