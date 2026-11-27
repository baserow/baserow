import flushPromises from 'flush-promises'
import { TestApp } from '@baserow/test/helpers/testApp'
import OAuthCallback from '@baserow/modules/integrations/oauthAccount/pages/oauthCallback.vue'
import { registerTestOAuthType } from '@baserow/test/unit/integrations/oauthAccount/testIntegrationType'

const MESSAGE_TYPE = 'baserow-test_oauth-oauth'

// The channel delivers on a later task.
const deliver = () => new Promise((resolve) => setTimeout(resolve, 20))

describe('OAuth account sign-in callback page', () => {
  let testApp = null
  let unregister = null
  let channel = null
  let received = null

  beforeEach(() => {
    testApp = new TestApp()
    unregister = registerTestOAuthType(testApp)
    testApp.authenticate({ id: 1, username: 'dev@baserow.io' })
    testApp.mock.onGet('/settings/').reply(200, {})
    vi.spyOn(window, 'close').mockImplementation(() => {})
    received = []
    // A real channel, as the page waiting for the sign-in has: what's posted
    // must be clonable.
    channel = new BroadcastChannel(MESSAGE_TYPE)
    channel.onmessage = (event) => received.push(event.data)
  })

  afterEach(async () => {
    channel.close()
    vi.restoreAllMocks()
    unregister()
    await testApp.afterEach()
  })

  test('finishes the sign-in and tells the waiting page', async () => {
    const integration = { id: 7, type: 'test_oauth', connected: true }
    testApp.mock
      .onPost('/integrations/oauth/test_oauth/complete/')
      .reply((config) => {
        expect(JSON.parse(config.data)).toEqual({
          state: 'abc',
          code: 'the-code',
          error: '',
          error_description: '',
        })
        return [200, { created: true, integration }]
      })

    const wrapper = await testApp.mount(OAuthCallback, {
      route: '/integrations/test_oauth/oauth-callback?state=abc&code=the-code',
    })
    await flushPromises()
    await deliver()

    expect(received).toEqual([
      {
        type: MESSAGE_TYPE,
        state: 'abc',
        created: true,
        integration,
        error: null,
      },
    ])
    expect(wrapper.text()).toContain('oauthAccountCallback.connected')
    expect(window.close).toHaveBeenCalled()
  })

  test('passes on the error the provider redirected back with', async () => {
    testApp.mock
      .onPost('/integrations/oauth/test_oauth/complete/')
      .reply((config) => {
        expect(JSON.parse(config.data)).toMatchObject({
          error: 'access_denied',
          error_description: 'ADMIN_ONLY',
        })
        return [
          400,
          {
            error: 'ERROR_OAUTH_ADMIN_CONSENT_REQUIRED',
            detail: 'https://login.example.com/adminconsent',
          },
        ]
      })

    const wrapper = await testApp.mount(OAuthCallback, {
      route:
        '/integrations/test_oauth/oauth-callback?state=abc&error=access_denied&error_description=ADMIN_ONLY',
    })
    await flushPromises()
    await deliver()

    expect(received).toEqual([
      {
        type: MESSAGE_TYPE,
        state: 'abc',
        created: false,
        integration: null,
        error: {
          code: 'ERROR_OAUTH_ADMIN_CONSENT_REQUIRED',
          detail: 'https://login.example.com/adminconsent',
        },
      },
    ])
    expect(wrapper.text()).toContain('oauthAccountErrors.adminConsentRequired')
  })

  test('an admin approving Baserow finishes no sign-in', async () => {
    const wrapper = await testApp.mount(OAuthCallback, {
      route: '/integrations/test_oauth/oauth-callback?admin_consent=True',
    })
    await flushPromises()
    await deliver()

    expect(testApp.mock.history.post).toEqual([])
    expect(received).toEqual([])
    expect(wrapper.text()).toContain('oauthAccountCallback.adminApproved')
  })

  test.each(['..%2F..%2Fuser%2Fdashboard%3F', 'smtp', 'does_not_exist'])(
    'a type that does not connect an account sends nothing (%s)',
    async (integrationType) => {
      const wrapper = await testApp.mount(OAuthCallback, {
        route: `/integrations/${integrationType}/oauth-callback?state=abc&code=x`,
      })
      await flushPromises()
      await deliver()

      expect(testApp.mock.history.post).toEqual([])
      expect(received).toEqual([])
      expect(wrapper.text()).toContain('oauthAccountErrors.failed')
    }
  )
})
