import { TestApp } from '@baserow/test/helpers/testApp'
import GoogleForm from '@baserow/modules/integrations/google/components/GoogleForm'
import GoogleGmailSendEmailServiceForm from '@baserow/modules/integrations/google/components/GoogleGmailSendEmailServiceForm'
import { GMAIL_SEND_SCOPE } from '@baserow/modules/integrations/google/serviceTypes'

describe('Google integration and Gmail forms', () => {
  let testApp
  let application
  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('application/forceCreate', {
      id: 100,
      name: 'Database',
      type: 'database',
      workspace: { id: 1 },
      tables: [],
    })
    application = testApp.store.getters['application/get'](100)
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  test('custom client is offered before saving without submitting an untouched secret', async () => {
    const wrapper = await testApp.mount(GoogleForm, {
      props: { application, defaultValues: {} },
    })
    expect(wrapper.vm.getFormValues()).toEqual({
      client_mode: 'custom',
      client_id: '',
    })
    expect(wrapper.text()).toContain('googleIntegration.saveFirst')
    expect(wrapper.html()).toMatchSnapshot()
  })

  test.each([false, true])(
    'Gmail requests consent only when its scope is missing: granted=%s',
    async (granted) => {
      await testApp.store.dispatch('integration/forceCreate', {
        application,
        integration: {
          id: 9,
          name: 'Google',
          type: 'google',
          connected: true,
          account_email: 'sender@example.com',
          granted_scopes: granted ? [GMAIL_SEND_SCOPE] : [],
        },
      })
      const wrapper = await testApp.mount(GoogleGmailSendEmailServiceForm, {
        props: { application, defaultValues: { integration_id: 9 } },
        global: {
          provide: {
            formulaComponent: { template: '<input />' },
            dataProvidersAllowed: [],
          },
        },
      })
      expect(wrapper.text().includes('googleGmail.consentRequired')).toBe(
        !granted
      )
      expect(wrapper.vm.getFormValues().integration_id).toBe(9)
    }
  )

  test('saved integration displays the callback URI and default OAuth client option', async () => {
    const integration = {
      id: 9,
      name: 'Google',
      type: 'google',
      connected: false,
      client_mode: 'default',
      client_id: '',
      has_client_secret: true,
      context_data: {
        redirect_uri: 'https://example.com/google-oauth-callback',
        default_client_available: true,
      },
    }
    await testApp.store.dispatch('integration/forceCreate', {
      application,
      integration,
    })
    const wrapper = await testApp.mount(GoogleForm, {
      props: { application, defaultValues: integration },
    })
    expect(wrapper.text()).toContain(
      'https://example.com/google-oauth-callback'
    )
    expect(wrapper.text()).toContain('googleIntegration.defaultClient')
    expect(wrapper.vm.getFormValues()).not.toHaveProperty('client_secret')
  })
})

describe('Google form in the integration editor', () => {
  test('the editor saves composition form values through its existing parent form', async () => {
    const { default: IntegrationEditForm } =
      await import('@baserow/modules/core/components/integrations/IntegrationEditForm')
    const testApp = new TestApp()
    try {
      await testApp.store.dispatch('application/forceCreate', {
        id: 101,
        type: 'database',
        name: 'Database',
        workspace: { id: 1 },
        tables: [],
      })
      const application = testApp.store.getters['application/get'](101)
      const wrapper = await testApp.mount(IntegrationEditForm, {
        props: {
          application,
          integrationType: testApp._app.$registry.get('integration', 'google'),
          defaultValues: {
            name: 'My account',
            client_mode: 'custom',
            client_id: 'google-client',
          },
        },
      })
      expect(wrapper.vm.getFormValues()).toEqual({
        name: 'My account',
        client_mode: 'custom',
        client_id: 'google-client',
      })
      await wrapper.find('input[type="password"]').setValue('new-secret')
      expect(wrapper.vm.getFormValues().client_secret).toBe('new-secret')
    } finally {
      await testApp.afterEach()
    }
  })
})
