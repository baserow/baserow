import flushPromises from 'flush-promises'

import OAuthAccountForm from '@baserow/modules/integrations/oauthAccount/components/OAuthAccountForm'
import { TestApp } from '@baserow/test/helpers/testApp'
import {
  TEST_OAUTH_TYPE,
  registerTestOAuthType,
} from '@baserow/test/unit/integrations/oauthAccount/testIntegrationType'

const MESSAGE_TYPE = 'baserow-test_oauth-oauth'
const BASE = '/integrations/oauth/test_oauth'
const AUTHORIZATION_URL = 'https://login.example.com/authorize?state=abc'

const connectedIntegration = (extra = {}) => ({
  id: 7,
  type: TEST_OAUTH_TYPE,
  name: 'Example (alice@example.com)',
  connected: true,
  account_email: 'alice@example.com',
  account_name: 'Alice',
  scopes: ['openid'],
  connected_at: '2026-11-20T10:00:00Z',
  connected_by_name: 'Alice',
  ...extra,
})

// What the callback page reports once the provider redirected back.
const report = (result, state = 'abc') => {
  const channel = new BroadcastChannel(MESSAGE_TYPE)
  channel.postMessage({ type: MESSAGE_TYPE, state, ...result })
  channel.close()
}

// The channel delivers on a later task.
const deliver = () => new Promise((resolve) => setTimeout(resolve, 20))

describe('OAuth account form', () => {
  let testApp = null
  let unregister = null
  let popup = null
  let application = null

  beforeEach(() => {
    testApp = new TestApp()
    unregister = registerTestOAuthType(testApp)
    application = { id: 3, integrations: [] }
    popup = { location: {}, closed: false, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(popup)
    testApp.mock.onGet(`${BASE}/config/`).reply(200, {
      configured: true,
      redirect_uri: 'https://b.io/integrations/test_oauth/oauth-callback',
      allow_account_switch: true,
      keep_connection_in_published_copies: true,
    })
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    unregister()
    await testApp.afterEach()
  })

  async function mountForm(props = {}, slots = {}) {
    const wrapper = await testApp.mount(OAuthAccountForm, {
      props: {
        application,
        defaultValues: {},
        integrationType: testApp
          .getRegistry()
          .get('integration', TEST_OAUTH_TYPE),
        ...props,
      },
      slots,
    })
    await flushPromises()
    return wrapper
  }

  const button = (wrapper, key) =>
    wrapper.findAll('button').find((b) => b.text().includes(key))

  test('explains an installation without an OAuth app', async () => {
    testApp.mock.reset()
    testApp.mock.onGet(`${BASE}/config/`).reply(200, {
      configured: false,
      redirect_uri: 'https://b.io/integrations/test_oauth/oauth-callback',
    })

    const wrapper = await mountForm()

    expect(wrapper.text()).toContain('oauthAccountForm.notConfigured')
    expect(wrapper.text()).toContain(
      'https://b.io/integrations/test_oauth/oauth-callback'
    )
    expect(button(wrapper, 'oauthAccountForm.signIn')).toBeUndefined()
  })

  test('signing in creates the integration and emits it', async () => {
    testApp.mock
      .onPost(`${BASE}/start/`)
      .reply(200, { authorization_url: AUTHORIZATION_URL })
    const wrapper = await mountForm({
      integrationName: 'Sales',
      serviceTypes: ['test_oauth_send_message'],
    })

    await button(wrapper, 'oauthAccountForm.signIn').trigger('click')
    // The popup opens on the click itself, before any request.
    expect(window.open).toHaveBeenCalledTimes(1)
    expect(window.open.mock.calls[0][1]).toMatch(/^baserow-test_oauth-oauth-/)
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      application_id: 3,
      integration_id: null,
      service_types: ['test_oauth_send_message'],
      name: 'Sales',
    })
    expect(popup.location.href).toBe(AUTHORIZATION_URL)

    // Another sign-in finishing doesn't end this one.
    report({ created: true, integration: connectedIntegration({ id: 8 }) }, 'x')
    await deliver()
    expect(wrapper.emitted('created')).toBeUndefined()

    const integration = connectedIntegration()
    report({ created: true, integration, error: null })
    await deliver()
    await flushPromises()

    expect(wrapper.emitted('created')).toEqual([[integration]])
    expect(application.integrations.map(({ id }) => id)).toEqual([7])
    expect(popup.close).toHaveBeenCalled()
  })

  test('an admin approval error offers the link to send the admin', async () => {
    testApp.mock
      .onPost(`${BASE}/start/`)
      .reply(200, { authorization_url: AUTHORIZATION_URL })
    const wrapper = await mountForm()

    await button(wrapper, 'oauthAccountForm.signIn').trigger('click')
    await flushPromises()
    report({
      integration: null,
      error: {
        code: 'ERROR_OAUTH_ADMIN_CONSENT_REQUIRED',
        detail: 'https://login.example.com/adminconsent',
      },
    })
    await deliver()
    await flushPromises()

    expect(wrapper.emitted('created')).toBeUndefined()
    expect(wrapper.text()).toContain('oauthAccountErrors.adminConsentRequired')
    expect(wrapper.find('.form-input__input').element.value).toBe(
      'https://login.example.com/adminconsent'
    )
  })

  test('a cancelled sign-in shows nothing', async () => {
    testApp.mock
      .onPost(`${BASE}/start/`)
      .reply(200, { authorization_url: AUTHORIZATION_URL })
    const wrapper = await mountForm()

    await button(wrapper, 'oauthAccountForm.signIn').trigger('click')
    await flushPromises()
    report({
      integration: null,
      error: { code: 'ERROR_OAUTH_SIGN_IN_CANCELLED', detail: null },
    })
    await deliver()
    await flushPromises()

    expect(wrapper.text()).not.toContain('oauthAccountForm.signInFailedTitle')
  })

  test('giving up on a pending sign-in stops waiting for it', async () => {
    testApp.mock
      .onPost(`${BASE}/start/`)
      .reply(200, { authorization_url: AUTHORIZATION_URL })
    const wrapper = await mountForm()

    await button(wrapper, 'oauthAccountForm.signIn').trigger('click')
    await flushPromises()
    await button(wrapper, 'action.cancel').trigger('click')
    await flushPromises()

    expect(button(wrapper, 'action.cancel')).toBeUndefined()
    expect(popup.close).toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('oauthAccountForm.signInFailedTitle')
  })

  test('a blocked popup is explained and starts no sign-in', async () => {
    window.open.mockReturnValue(null)
    const wrapper = await mountForm()

    await button(wrapper, 'oauthAccountForm.signIn').trigger('click')
    await flushPromises()

    expect(testApp.mock.history.post).toEqual([])
    expect(wrapper.text()).toContain('oauthAccountErrors.popupBlocked')
  })

  test('a sign-in that fails to start closes the popup', async () => {
    testApp.mock.onPost(`${BASE}/start/`).reply(400, {
      error: 'ERROR_OAUTH_NOT_CONFIGURED',
      detail: '',
    })
    const wrapper = await mountForm()

    await button(wrapper, 'oauthAccountForm.signIn').trigger('click')
    await flushPromises()

    expect(popup.close).toHaveBeenCalled()
    expect(wrapper.text()).toContain('oauthAccountErrors.notConfigured')
  })

  test('shows the connected account and disconnects it', async () => {
    const integration = connectedIntegration()
    application.integrations.push(integration)
    testApp.mock
      .onPost(`${BASE}/7/disconnect/`)
      .reply(200, connectedIntegration({ connected: false }))
    const wrapper = await mountForm({ defaultValues: integration })

    expect(wrapper.text()).toContain('alice@example.com')
    expect(wrapper.text()).toContain('oauthAccountForm.connected')
    expect(wrapper.text()).toContain('oauthAccountForm.publishedNote')
    expect(wrapper.text()).toContain('oauthAccountForm.reconnectNote')

    await button(wrapper, 'oauthAccountForm.disconnect').trigger('click')
    await flushPromises()

    expect(application.integrations[0].connected).toBe(false)
  })

  test('the notes follow what the provider allows', async () => {
    testApp.mock.reset()
    testApp.mock.onGet(`${BASE}/config/`).reply(200, {
      configured: true,
      redirect_uri: '',
      allow_account_switch: false,
      keep_connection_in_published_copies: false,
    })
    const wrapper = await mountForm({ defaultValues: connectedIntegration() })

    expect(wrapper.text()).toContain(
      'oauthAccountForm.reconnectSameAccountNote'
    )
    expect(wrapper.text()).not.toContain('oauthAccountForm.publishedNote')
  })

  test('reconnecting sends the integration, not the application', async () => {
    const integration = connectedIntegration({ connected: false })
    application.integrations.push(integration)
    testApp.mock
      .onPost(`${BASE}/start/`)
      .reply(200, { authorization_url: AUTHORIZATION_URL })
    const wrapper = await mountForm({ defaultValues: integration })

    expect(wrapper.text()).toContain('oauthAccountForm.reconnectNeeded')
    await button(wrapper, 'oauthAccountForm.reconnect').trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.post[0].data)).toMatchObject({
      application_id: null,
      integration_id: 7,
    })
    report({
      created: false,
      integration: connectedIntegration({ account_email: 'bob@example.com' }),
      error: null,
    })
    await deliver()
    await flushPromises()

    expect(wrapper.emitted('created')).toBeUndefined()
    expect(application.integrations[0].account_email).toBe('bob@example.com')
  })

  test('a provider adds its own fields in the extras slot', async () => {
    const wrapper = await mountForm(
      {},
      { extras: '<div class="provider-extras">Client id</div>' }
    )

    expect(wrapper.find('.provider-extras').exists()).toBe(true)
  })

  test('a provider can offer to sign in with an app of the integration', async () => {
    testApp.mock.reset()
    testApp.mock.onGet(`${BASE}/config/`).reply(200, {
      configured: false,
      redirect_uri: '',
    })
    const type = testApp.getRegistry().get('integration', TEST_OAUTH_TYPE)
    vi.spyOn(type, 'canSignIn').mockImplementation((config, integration) =>
      Boolean(integration.own_client_id)
    )

    const wrapper = await mountForm({
      defaultValues: connectedIntegration({ own_client_id: 'own' }),
    })

    expect(wrapper.text()).not.toContain('oauthAccountForm.notConfigured')
    expect(button(wrapper, 'oauthAccountForm.reconnect')).toBeDefined()
  })

  test('the service puts the type in the path as one segment', async () => {
    const { default: OAuthAccountService } =
      await import('@baserow/modules/integrations/oauthAccount/services/oauthAccount')
    testApp.mock.onGet(/config/).reply(200, {})

    await OAuthAccountService(testApp._app.$client, '../user').getConfig()

    expect(testApp.mock.history.get.at(-1).url).toBe(
      '/integrations/oauth/..%2Fuser/config/'
    )
  })
})
