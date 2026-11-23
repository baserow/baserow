import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import EnterpriseFeatures from '@baserow_enterprise/features'

const CONTINUE = 'agent_application.continue_triggered_conversation'

const team = (id, name) => ({
  subject_type: 'baserow_enterprise.Team',
  subject_id: id,
  subject: { id, name },
})

describe('agent participation settings', () => {
  let app, agent

  beforeEach(async () => {
    app = new TestApp()
    await app.store.dispatch('workspace/forceCreate', { id: 1, name: 'W' })
    agent = await app.store.dispatch('application/forceCreate', {
      id: 8,
      name: 'Support agent',
      type: 'agent',
      workspace: { id: 1 },
    })
  })

  afterEach(async () => {
    await app.afterEach()
    vi.restoreAllMocks()
  })

  const endpoint = '/agent/8/permissions/'
  const editor = { role: 'EDITOR', subjects: [] }
  const nobody = { role: 'NOBODY', subjects: [] }

  function mockRules({ chat = editor, approve = editor, ...rest } = {}) {
    app.mock
      .onGet(endpoint)
      .reply(200, { chat, approve, continue: rest.continue ?? nobody })
  }

  async function mountSidebar({ licensed = true, editable = true } = {}) {
    vi.spyOn(app.nuxtApp.$licenseHandler, 'hasFeature').mockImplementation(
      (feature) => licensed && feature === EnterpriseFeatures.RBAC
    )
    const wrapper = await app.mount(AgentConfigurationSidebar, {
      props: {
        name: 'Support agent',
        configuration: {
          instructions: 'Be helpful.',
          available_trigger_types: ['periodic'],
          errors: {},
        },
        errors: {},
        enabledModels: {},
        editable,
      },
      global: {
        provide: { agentApplication: ref(agent) },
        stubs: {
          PaidFeaturesModal: {
            template: '<div v-if="open" class="paywall"/>',
            data: () => ({ open: false }),
            methods: {
              show() {
                this.open = true
              },
            },
          },
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  const sectionItem = (wrapper, label) =>
    wrapper
      .findAll('.menu-list__item-button')
      .find((button) => button.text().includes(label))

  async function openPermissions(wrapper) {
    await sectionItem(wrapper, 'agentPermissions.section').trigger('click')
    await flushPromises()
  }

  async function openRoles(wrapper, index) {
    await wrapper
      .findAll('.control')
      [index].get('.dropdown__selected')
      .trigger('click')
    return wrapper.findAll('.control')[index].findAll('.select__item')
  }

  async function choose(wrapper, index, roleLabel) {
    const items = await openRoles(wrapper, index)
    await items
      .find((item) => item.text().includes(roleLabel))
      .get('.select__item-link')
      .trigger('click')
    await flushPromises()
  }

  const selectedRoles = (wrapper) =>
    wrapper.findAll('.dropdown__selected-text').map((item) => item.text())

  test('lists Permissions after Workspace access with three settings and their defaults', async () => {
    mockRules()
    const wrapper = await mountSidebar()
    const labels = wrapper
      .findAll('.menu-list__item-label')
      .map((label) => label.text())

    expect(labels.indexOf('agentPermissions.section')).toBe(
      labels.indexOf('agent.workspaceAccess') + 1
    )
    expect(
      sectionItem(wrapper, 'agentPermissions.section')
        .find('.icon--error')
        .exists()
    ).toBe(false)

    await openPermissions(wrapper)

    expect(
      wrapper.findAll('.control__label').map((label) => label.text())
    ).toEqual([
      expect.stringContaining('agentPermissions.chat'),
      expect.stringContaining('agentPermissions.approve'),
      expect.stringContaining('agentPermissions.continue'),
    ])
    expect(selectedRoles(wrapper)).toEqual([
      'agentPermissions.EDITOR',
      'agentPermissions.EDITOR',
      'agentPermissions.NOBODY',
    ])
    const defaults = async (index) =>
      (await openRoles(wrapper, index))
        .filter((item) => item.text().includes('agentPermissions.default'))
        .map((item) => item.get('.select__item-name').text())
    expect(await defaults(0)).toEqual(['agentPermissions.EDITOR'])
    expect(await defaults(2)).toEqual(['agentPermissions.NOBODY'])
    expect(app.mock.history.get.filter(({ url }) => url === endpoint)).toEqual([
      expect.anything(),
    ])
  })

  test('offers no Nobody option for approvals, and lets chat be turned off without a trigger', async () => {
    mockRules()
    app.mock.onPut(endpoint + 'chat/').reply(200, nobody)
    const wrapper = await mountSidebar()
    await openPermissions(wrapper)

    expect(
      (await openRoles(wrapper, 1)).map((item) =>
        item.get('.select__item-name').text()
      )
    ).not.toContain('agentPermissions.NOBODY')

    await choose(wrapper, 0, 'agentPermissions.NOBODY')

    expect(JSON.parse(app.mock.history.put[0].data)).toEqual(nobody)
    expect(selectedRoles(wrapper)[0]).toBe('agentPermissions.NOBODY')
    expect(document.querySelector('.modal__box')).toBeNull()
  })

  test('warns under a setting whose specific people are all gone', async () => {
    mockRules({ approve: { role: 'CUSTOM', subjects: [] } })
    const wrapper = await mountSidebar()
    await openPermissions(wrapper)

    expect(
      wrapper.findAll('.control__messages--warning').map((item) => item.text())
    ).toEqual(['agentPermissions.chooseSubjects'])
  })

  test('without the licence, shows what applies, locked, and opens the RBAC paywall', async () => {
    mockRules({ chat: nobody })
    const wrapper = await mountSidebar({ licensed: false })

    expect(
      sectionItem(wrapper, 'agentPermissions.section')
        .find('.icon--error')
        .exists()
    ).toBe(false)
    await openPermissions(wrapper)

    const locked = wrapper.findAll('.control button')
    expect(locked.map((button) => button.text())).toEqual([
      'agentPermissions.EVERYONE',
      'agentPermissions.EVERYONE',
      'agentPermissions.NOBODY',
    ])
    expect(wrapper.text()).toContain('agentPermissions.unlicensedNote')
    await locked[2].trigger('click')
    expect(wrapper.find('.paywall').exists()).toBe(true)
    expect(app.mock.history.get.map(({ url }) => url)).not.toContain(endpoint)
  })

  test('renders saved roles for a read-only configuration viewer', async () => {
    mockRules({
      chat: { role: 'BUILDER', subjects: [] },
      approve: { role: 'ADMIN', subjects: [] },
    })
    const wrapper = await mountSidebar({ editable: false })
    await openPermissions(wrapper)

    expect(
      wrapper
        .findAll('.dropdown--disabled .dropdown__selected-text')
        .map((item) => item.text())
    ).toEqual([
      'fieldPermissionModal.builderTitle',
      'fieldPermissionModal.adminTitle',
      'agentPermissions.NOBODY',
    ])
  })

  test('disables every setting while one saves', async () => {
    mockRules()
    let finishChat
    app.mock.onPut(endpoint + 'chat/').reply(
      () =>
        new Promise((resolve) => {
          finishChat = resolve
        })
    )
    const wrapper = await mountSidebar()
    await openPermissions(wrapper)
    await choose(wrapper, 0, 'fieldPermissionModal.builderTitle')

    expect(wrapper.findAll('.dropdown--disabled')).toHaveLength(3)
    finishChat([200, { role: 'BUILDER', subjects: [] }])
    await flushPromises()
    expect(wrapper.findAll('.dropdown--disabled')).toHaveLength(0)
    expect(selectedRoles(wrapper)[0]).toBe('fieldPermissionModal.builderTitle')
  })

  test('restores the saved role when an immediate change fails', async () => {
    mockRules()
    app.dontFailOnErrorResponses()
    app.mock.onPut(endpoint + 'approve/').reply(500, {})
    const wrapper = await mountSidebar()
    await openPermissions(wrapper)
    await choose(wrapper, 1, 'fieldPermissionModal.builderTitle')

    expect(app.mock.history.put).toHaveLength(1)
    expect(selectedRoles(wrapper)[1]).toBe('agentPermissions.EDITOR')
    expect(wrapper.findAll('.dropdown--disabled')).toHaveLength(0)
  })

  test('applies a removal from an existing custom rule without a separate save', async () => {
    const support = team(21, 'Support')
    const finance = team(22, 'Finance')
    const rule = { role: 'CUSTOM', subjects: [support, finance] }
    mockRules({ approve: rule })
    app.mock
      .onPut(endpoint + 'approve/')
      .reply(200, { ...rule, subjects: [finance] })
    const wrapper = await mountSidebar()
    await openPermissions(wrapper)
    await wrapper.get('.control button').trigger('click')
    const modal = () => document.querySelector('.modal__box')
    modal().querySelector('.field-permission-subjects__item button').click()
    await flushPromises()

    expect(JSON.parse(app.mock.history.put[0].data)).toEqual({
      role: 'CUSTOM',
      subjects: [
        { subject_type: finance.subject_type, subject_id: finance.subject_id },
      ],
    })
    expect(
      modal().querySelector('.field-permission-subjects__list').textContent
    ).toContain('Finance')
    expect(
      modal().querySelector('.field-permission-subjects__item button').disabled
    ).toBe(true)
  })

  test('starts a custom rule with the first person or team', async () => {
    const teamType = 'baserow_enterprise.Team'
    mockRules()
    app.mock.onGet(endpoint + 'options/').reply(200, {
      count: 1,
      results: [
        {
          subject_type: teamType,
          subject_id: 21,
          name: 'Support',
          subject_count: 2,
        },
      ],
    })
    app.mock
      .onPut(endpoint + 'continue/')
      .reply(200, { role: 'CUSTOM', subjects: [team(21, 'Support')] })
    const wrapper = await mountSidebar()
    await openPermissions(wrapper)
    await choose(wrapper, 2, 'agentPermissions.CUSTOM')
    const modal = () => document.querySelector('.modal__box')
    expect(modal()).toBeTruthy()
    expect(app.mock.history.put).toHaveLength(0)
    modal().querySelector('.dropdown__selected').click()
    await flushPromises()
    modal().querySelector('.select__item-link').click()
    await flushPromises()
    expect(JSON.parse(app.mock.history.put[0].data)).toEqual({
      role: 'CUSTOM',
      subjects: [{ subject_type: teamType, subject_id: 21 }],
    })
    expect(
      modal().querySelector('.field-permission-subjects__item button').disabled
    ).toBe(true)
    expect(wrapper.findAll('.control')[2].text()).toContain(
      'agentPermissions.managePeople'
    )
  })

  test('the permission manager decides who continues and only refuses the other operations', () => {
    const manager = app
      .getRegistry()
      .get('permissionManager', 'agent_participation')
    const chat = 'agent_application.create_message'
    const permissions = {
      denied: { [chat]: [8] },
      allowed: { [CONTINUE]: [8] },
    }

    expect(manager.hasPermission(permissions, CONTINUE, { id: 8 })).toBe(true)
    expect(manager.hasPermission(permissions, CONTINUE, { id: 9 })).toBe(false)
    expect(manager.hasPermission(permissions, chat, { id: 8 })).toBe(false)
    expect(manager.hasPermission(permissions, chat, { id: 9 })).toBeNull()
  })
})
