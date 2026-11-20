import flushPromises from 'flush-promises'

import MicrosoftIntegrationForm from '@baserow/modules/integrations/microsoft/components/MicrosoftIntegrationForm'
import { TestApp } from '@baserow/test/helpers/testApp'

const connected = (extra = {}) => ({
  id: 7,
  type: 'microsoft',
  name: 'Microsoft (alice@contoso.com)',
  connected: true,
  account_email: 'alice@contoso.com',
  account_name: 'Alice',
  account_type: 'work_or_school',
  scopes: ['User.Read'],
  connected_at: '2026-11-20T10:00:00Z',
  connected_by_name: 'Alice',
  ...extra,
})

describe('Microsoft integration', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.mock.onGet('/integrations/oauth/microsoft/config/').reply(200, {
      configured: true,
      redirect_uri: 'https://b.io/integrations/microsoft/oauth-callback',
      allow_account_switch: true,
      keep_connection_in_published_copies: true,
    })
  })

  afterEach(async () => {
    // Restored here, so a failing assertion can't leak a spy into later tests.
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  const integrationType = () =>
    testApp.getRegistry().get('integration', 'microsoft')

  test('is an OAuth account type that signs in with Microsoft', () => {
    const type = integrationType()

    expect(type.providerName).toBe('Microsoft')
    expect(type.createsItself).toBe(true)
    expect(type.getDefaultValues()).toEqual({ name: '' })
    expect(type.getErrorMessage({ connected: false })).toBe(
      'oauthAccountIntegrationType.errorNotConnected'
    )
  })

  async function mountForm(defaultValues) {
    const wrapper = await testApp.mount(MicrosoftIntegrationForm, {
      props: {
        application: { id: 3, integrations: [defaultValues] },
        defaultValues,
        integrationType: integrationType(),
      },
    })
    await flushPromises()
    return wrapper
  }

  test('shows whether the account is a work or a personal one', async () => {
    const work = await mountForm(connected())
    expect(work.text()).toContain('alice@contoso.com')
    expect(work.text()).toContain('microsoftIntegrationForm.workAccount')

    const personal = await mountForm(connected({ account_type: 'personal' }))
    expect(personal.text()).toContain(
      'microsoftIntegrationForm.personalAccount'
    )
  })

  test('adds no separator when the account has no email', async () => {
    const wrapper = await mountForm(connected({ account_email: '' }))

    const detail = wrapper.find('.oauth-account-form__account-detail').text()
    expect(detail).toBe('microsoftIntegrationForm.workAccount')
  })

  test('passes the sign-in through to the shared form', async () => {
    const popup = { location: {}, closed: false, close: vi.fn() }
    vi.spyOn(window, 'open').mockReturnValue(popup)
    testApp.mock.onPost('/integrations/oauth/microsoft/start/').reply(200, {
      authorization_url:
        'https://login.microsoftonline.com/common/oauth2/v2.0/authorize?state=abc',
    })
    const wrapper = await mountForm({})

    const signIn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('oauthAccountForm.signIn'))
    await signIn.trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.post[0].data)).toMatchObject({
      application_id: 3,
      integration_id: null,
    })
    expect(popup.location.href).toContain('login.microsoftonline.com')
  })
})
