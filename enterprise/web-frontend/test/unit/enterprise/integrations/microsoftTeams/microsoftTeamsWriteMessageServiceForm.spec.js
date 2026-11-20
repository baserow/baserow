import { defineComponent } from 'vue'
import { vi } from 'vitest'
import flushPromises from 'flush-promises'

import { TestApp } from '@baserow/test/helpers/testApp'
import MicrosoftTeamsWriteMessageServiceForm from '@baserow_enterprise/integrations/microsoftTeams/components/services/MicrosoftTeamsWriteMessageServiceForm'

const TEAMS_SCOPES = [
  'User.Read',
  'ChannelMessage.Send',
  'ChatMessage.Send',
  'Team.ReadBasic.All',
  'Channel.ReadBasic.All',
  'Chat.ReadBasic',
]

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
  scopes: TEAMS_SCOPES,
  ...extra,
})

const literal = (id) => ({ formula: `'${id}'`, mode: 'simple' })

describe('Microsoft Teams write message service form', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function mountForm(defaultValues = {}, integrationValues = {}) {
    const application = {
      id: 3,
      workspace: { id: 1 },
      integrations: [integration(integrationValues)],
    }
    const wrapper = await testApp.mount(MicrosoftTeamsWriteMessageServiceForm, {
      props: {
        application,
        defaultValues: { integration_id: 7, ...defaultValues },
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

  test('asks for the Teams permissions when the integration is created', async () => {
    testApp.mock.onGet(/microsoft-teams\/7\/teams\//).reply(200, [])
    const wrapper = await mountForm()

    expect(
      wrapper.findComponent(IntegrationDropdownStub).props('serviceTypes')
    ).toEqual(['microsoft_teams_write_message'])
    expect(wrapper.text()).toContain('microsoftTeamsForm.sentAs')
  })

  test('picks a team, then one of its channels', async () => {
    testApp.mock.onGet('/integrations/microsoft-teams/7/teams/').reply(200, [
      { id: 't1', name: 'Marketing' },
      { id: 't2', name: 'Sales' },
    ])
    testApp.mock
      .onGet('/integrations/microsoft-teams/7/teams/t1/channels/')
      .reply(200, [
        { id: '19:general@thread.tacv2', name: 'General', membership_type: '' },
      ])
    const wrapper = await mountForm()

    expect(wrapper.vm.teams.map(({ name }) => name)).toEqual([
      'Marketing',
      'Sales',
    ])
    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(2)

    wrapper.vm.pickTeam('t1')
    await flushPromises()
    wrapper.vm.pickChannel('19:general@thread.tacv2')

    expect(wrapper.vm.values.team_id).toEqual(literal('t1'))
    expect(wrapper.vm.values.channel_id).toEqual(
      literal('19:general@thread.tacv2')
    )
    expect(wrapper.vm.values.destination_label).toBe('General · Marketing')
    // Only the message is a formula input: the team and channel are lists.
    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(1)
  })

  test('picking another team clears the channel', async () => {
    testApp.mock.onGet(/teams\/$/).reply(200, [{ id: 't1', name: 'A' }])
    testApp.mock.onGet(/channels\/$/).reply(200, [])
    const wrapper = await mountForm({
      team_id: literal('t1'),
      channel_id: literal('c1'),
      destination_label: 'General · A',
    })

    wrapper.vm.pickTeam('t2')

    expect(wrapper.vm.values.channel_id.formula).toBe('')
    expect(wrapper.vm.values.destination_label).toBe('')
  })

  test('switches to a chat and picks one', async () => {
    testApp.mock.onGet(/teams\/$/).reply(200, [])
    testApp.mock
      .onGet('/integrations/microsoft-teams/7/chats/')
      .reply(200, [{ id: 'c1', name: 'Bob', chat_type: 'oneOnOne' }])
    const wrapper = await mountForm()

    wrapper.vm.selectDestinationType(1)
    await flushPromises()
    wrapper.vm.pickChat('c1')

    expect(wrapper.vm.values.destination_type).toBe('chat')
    expect(wrapper.vm.values.chat_id).toEqual(literal('c1'))
    expect(wrapper.vm.values.destination_label).toBe('Bob')
  })

  test('a destination can be an id or a formula', async () => {
    testApp.mock.onGet(/chats\/$/).reply(200, [])
    const wrapper = await mountForm({ destination_type: 'chat' })
    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(1)

    wrapper.vm.toggleFormula('chat_id')
    await flushPromises()

    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(2)
    expect(wrapper.text()).toContain('microsoftTeamsForm.pickFromList')
  })

  test('offers the formula switch once an account is chosen', async () => {
    testApp.mock.onGet(/teams\/$/).reply(200, [])
    const wrapper = await mountForm({ integration_id: null })
    expect(wrapper.text()).not.toContain('microsoftTeamsForm.useFormula')

    wrapper
      .findComponent(IntegrationDropdownStub)
      .vm.$emit('update:modelValue', 7)
    await flushPromises()

    expect(wrapper.text()).toContain('microsoftTeamsForm.useFormula')
  })

  test('a destination from data stays a formula', async () => {
    const wrapper = await mountForm({
      destination_type: 'chat',
      chat_id: { formula: "get('data_source.Chats.0.id')", mode: 'simple' },
    })

    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(2)
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('a slower answer for an earlier team does not replace the list', async () => {
    const later = (ms, data) => () =>
      new Promise((resolve) => setTimeout(() => resolve([200, data]), ms))
    testApp.mock.onGet('/integrations/microsoft-teams/7/teams/').reply(200, [
      { id: 'tA', name: 'A' },
      { id: 'tB', name: 'B' },
    ])
    testApp.mock
      .onGet('/integrations/microsoft-teams/7/teams/tA/channels/')
      .reply(later(80, [{ id: 'cA', name: 'Channel of A' }]))
    testApp.mock
      .onGet('/integrations/microsoft-teams/7/teams/tB/channels/')
      .reply(later(10, [{ id: 'cB', name: 'Channel of B' }]))
    const wrapper = await mountForm()

    wrapper.vm.pickTeam('tA')
    // Team A's channels are asked for, and answer last.
    await flushPromises()
    expect(testApp.mock.history.get.map(({ url }) => url)).toContain(
      '/integrations/microsoft-teams/7/teams/tA/channels/'
    )
    wrapper.vm.pickTeam('tB')
    await new Promise((resolve) => setTimeout(resolve, 150))
    await flushPromises()

    expect(wrapper.vm.channels.map(({ id }) => id)).toEqual(['cB'])
    expect(wrapper.vm.loading.channels).toBe(false)
  })

  test('a formula restored by undo is shown as a formula', async () => {
    testApp.mock.onGet(/teams\/$/).reply(200, [{ id: 't1', name: 'A' }])
    testApp.mock.onGet(/channels\/$/).reply(200, [])
    const wrapper = await mountForm({ team_id: literal('t1') })
    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(1)

    await wrapper.setProps({
      defaultValues: {
        integration_id: 7,
        team_id: { formula: "get('previous_node.1.team')", mode: 'simple' },
      },
    })
    await wrapper.vm.reset(true)
    await flushPromises()

    // The team and the channel (its team isn't a picked one) are formulas.
    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(3)
  })

  test('asks to grant access when the Teams permissions are missing', async () => {
    const wrapper = await mountForm({ missing_scopes: ['ChatMessage.Send'] })

    expect(wrapper.text()).toContain('microsoftTeamsForm.grantAccess')
    // Without the permissions there's nothing to list.
    expect(testApp.mock.history.get).toHaveLength(0)
    expect(wrapper.findAllComponents(InjectedFormulaInputStub)).toHaveLength(3)
  })

  test('lists again once access is granted', async () => {
    testApp.mock.onGet('/integrations/microsoft-teams/7/teams/').reply(200, [])
    const wrapper = await mountForm({ missing_scopes: ['ChatMessage.Send'] })
    const popup = { close: vi.fn() }
    const open = vi.spyOn(window, 'open').mockReturnValue(popup)
    const signIn = vi.fn().mockResolvedValue({ created: false })
    wrapper.vm.oauth.signIn = signIn

    await wrapper.vm.grantAccess()
    await flushPromises()
    open.mockRestore()

    expect(signIn).toHaveBeenCalledWith(
      expect.objectContaining({
        popup,
        serviceTypes: ['microsoft_teams_write_message'],
      })
    )
    // The saved service still lists the old missing permissions.
    expect(wrapper.text()).not.toContain('microsoftTeamsForm.grantAccess')
    expect(testApp.mock.history.get).toHaveLength(1)
  })

  test('refuses a personal account', async () => {
    const wrapper = await mountForm({}, { account_type: 'personal' })

    expect(wrapper.text()).toContain('microsoftTeamsForm.personalAccount')
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('shows why a list could not be loaded', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet(/teams\/$/).reply(400, {
      error: 'ERROR_MICROSOFT_TEAMS_PICKER',
      detail: 'The connected Microsoft account must be connected again.',
    })
    const wrapper = await mountForm()

    expect(wrapper.vm.pickerErrors.teams).toBe(
      'The connected Microsoft account must be connected again.'
    )
  })
})
