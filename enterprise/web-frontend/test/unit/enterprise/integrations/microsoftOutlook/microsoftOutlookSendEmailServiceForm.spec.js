import { defineComponent, reactive } from 'vue'
import { vi } from 'vitest'
import flushPromises from 'flush-promises'

import { TestApp } from '@baserow/test/helpers/testApp'
import MicrosoftOutlookSendEmailServiceForm from '@baserow_enterprise/integrations/microsoftOutlook/components/services/MicrosoftOutlookSendEmailServiceForm'

const InjectedFormulaInputStub = defineComponent({
  name: 'InjectedFormulaInput',
  props: { modelValue: { type: Object, default: null } },
  template: '<div class="formula-input-stub" />',
})

const IntegrationDropdownStub = defineComponent({
  name: 'IntegrationDropdown',
  props: {
    modelValue: { type: Number, default: null },
    serviceTypes: { type: Array, default: () => [] },
  },
  template: '<div class="integration-dropdown-stub" />',
})

const integration = (extra = {}) => ({
  id: 7,
  type: 'microsoft',
  name: 'Microsoft',
  connected: true,
  account_email: 'alice@contoso.com',
  account_name: 'Alice',
  account_type: 'work_or_school',
  scopes: ['User.Read', 'Mail.Send'],
  ...extra,
})

const formula = (value) => ({ formula: value, mode: 'simple' })

describe('Microsoft Outlook send email service form', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountForm(
    defaultValues = {},
    integrationValues = {},
    otherIntegrations = []
  ) {
    // Reactive, like the store's applications.
    const application = reactive({
      id: 3,
      workspace: { id: 1 },
      integrations: [integration(integrationValues), ...otherIntegrations],
    })
    const wrapper = await testApp.mount(MicrosoftOutlookSendEmailServiceForm, {
      props: {
        application,
        defaultValues: {
          integration_id: 7,
          required_scopes: ['Mail.Send'],
          ...defaultValues,
        },
      },
      global: {
        stubs: {
          InjectedFormulaInput: InjectedFormulaInputStub,
          IntegrationDropdown: IntegrationDropdownStub,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  test('asks for the mail permission when the integration is created', async () => {
    const wrapper = await mountForm()

    expect(
      wrapper.findComponent(IntegrationDropdownStub).props('serviceTypes')
    ).toEqual(['microsoft_outlook_send_email'])
    expect(wrapper.text()).toContain('microsoftOutlookForm.sentFrom')
    expect(wrapper.text()).not.toContain('microsoftOutlookForm.grantAccess')
  })

  test('shows the recipients, subject and body as formulas', async () => {
    const wrapper = await mountForm({
      to_emails: formula("'bob@example.com'"),
      cc_emails: formula("'carol@example.com'"),
      bcc_emails: formula(''),
      subject: formula("'Hello'"),
      body_type: 'html',
      body: formula("'<p>Hi</p>'"),
    })

    const inputs = wrapper.findAllComponents(InjectedFormulaInputStub)
    expect(inputs.map((input) => input.props('modelValue'))).toEqual([
      formula("'bob@example.com'"),
      formula("'carol@example.com'"),
      formula(''),
      formula("'Hello'"),
      formula("'<p>Hi</p>'"),
    ])
    expect(wrapper.vm.getFormValues()).toEqual({
      integration_id: 7,
      to_emails: formula("'bob@example.com'"),
      cc_emails: formula("'carol@example.com'"),
      bcc_emails: formula(''),
      subject: formula("'Hello'"),
      body_type: 'html',
      body: formula("'<p>Hi</p>'"),
    })
  })

  test('defaults to a plain text body', async () => {
    const wrapper = await mountForm()

    expect(wrapper.vm.values.body_type).toBe('plain')
  })

  test('accepts a personal account', async () => {
    const wrapper = await mountForm({}, { account_type: 'personal' })

    expect(wrapper.text()).not.toContain('personalAccount')
    expect(wrapper.text()).not.toContain('microsoftOutlookForm.grantAccess')
  })

  test('asks to grant access when the mail permission is missing', async () => {
    const wrapper = await mountForm({}, { scopes: ['User.Read'] })

    expect(wrapper.text()).toContain('microsoftOutlookForm.grantAccessTitle')
  })

  test('checks the permission of the integration that is picked', async () => {
    // Integration 8 was only granted access for Teams.
    const teamsOnly = integration({ id: 8, scopes: ['ChatMessage.Send'] })
    const wrapper = await mountForm({ integration_id: 8 }, {}, [teamsOnly])
    expect(wrapper.text()).toContain('microsoftOutlookForm.grantAccessTitle')

    await wrapper.setData({
      values: { ...wrapper.vm.values, integration_id: 7 },
    })

    expect(wrapper.text()).not.toContain('microsoftOutlookForm.grantAccess')
  })

  test('asks to reconnect a disconnected account', async () => {
    const wrapper = await mountForm({}, { connected: false })

    expect(wrapper.text()).toContain('microsoftOutlookForm.reconnectTitle')
  })

  test('hides the notice once access is granted', async () => {
    const wrapper = await mountForm({}, { scopes: ['User.Read'] })
    const popup = { close: vi.fn() }
    const open = vi.spyOn(window, 'open').mockReturnValue(popup)
    // Like the real sign-in, it stores the integration with what was granted.
    const signIn = vi.fn().mockImplementation(async ({ application }) => {
      await testApp.store.dispatch('integration/forceUpdate', {
        application,
        integration: application.integrations[0],
        values: { scopes: ['User.Read', 'Mail.Send'] },
      })
      return { created: false }
    })
    wrapper.vm.oauth.signIn = signIn

    await wrapper.vm.grantAccess()
    await flushPromises()
    open.mockRestore()

    expect(signIn).toHaveBeenCalledWith(
      expect.objectContaining({
        popup,
        serviceTypes: ['microsoft_outlook_send_email'],
      })
    )
    expect(wrapper.text()).not.toContain('microsoftOutlookForm.grantAccess')
  })
})
