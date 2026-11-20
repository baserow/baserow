import { flushPromises } from '@vue/test-utils'
import { createSSRApp, defineComponent, ref } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import EnterpriseFeatures from '@baserow_enterprise/features'

const CONTINUE = 'agent_application.continue_triggered_conversation'

const periodicTrigger = (enabled) => ({
  id: 1,
  type: 'periodic',
  name: '',
  enabled,
  message: { formula: "'Tick'", mode: 'simple', version: '0.1' },
  service: {
    id: 5,
    type: 'periodic',
    interval: 'HOUR',
    minute: 0,
    hour: 0,
    day_of_week: 0,
    day_of_month: 1,
    timezone: 'UTC',
    schema: null,
  },
  on_overlap: 'skip',
  last_fired_on: null,
  last_skipped_on: null,
  last_skipped_reason: '',
})

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

  const endpoint = '/agent-permissions/8/'
  const editor = { role: 'EDITOR', subjects: [] }
  const nobody = { role: 'NOBODY', subjects: [] }

  function mockRules({ chat = editor, approve = editor, ...rest } = {}) {
    app.mock
      .onGet(endpoint)
      .reply(200, { chat, approve, continue: rest.continue ?? nobody })
  }

  async function mountSidebar({
    licensed = true,
    editable = true,
    triggers = [],
  } = {}) {
    vi.spyOn(app.nuxtApp.$licenseHandler, 'hasFeature').mockImplementation(
      (feature) => licensed && feature === EnterpriseFeatures.RBAC
    )
    const dispatch = app.store.dispatch.bind(app.store)
    vi.spyOn(app.store, 'dispatch').mockImplementation((type, payload) =>
      type === 'workspace/forceFetchPermissions'
        ? Promise.resolve()
        : dispatch(type, payload)
    )
    app.mock.onGet('/agent/8/triggers/').reply(200, triggers)
    app.mock.onGet('/agent/8/trigger-types/').reply(200, [])
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

  const sectionError = (wrapper) =>
    sectionItem(wrapper, 'agentPermissions.section')
      .find('.icon--error')
      .attributes('aria-label')

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

  test('marks the section while chat is off and no trigger is enabled, even when closed', async () => {
    mockRules({ chat: nobody })
    app.mock.onPatch('/agent/8/triggers/1/').reply(200, periodicTrigger(true))
    const wrapper = await mountSidebar({ triggers: [periodicTrigger(false)] })

    expect(sectionError(wrapper)).toBe('agentPermissions.nobodyCanInteract')

    await sectionItem(wrapper, 'agent.whenItRuns').trigger('click')
    await wrapper.get('.agent-trigger-card__switch').trigger('click')
    await flushPromises()
    await wrapper.get('button[aria-label="action.back"]').trigger('click')

    expect(
      sectionItem(wrapper, 'agentPermissions.section')
        .find('.icon--error')
        .exists()
    ).toBe(false)
  })

  test('marks the section when specific people are chosen but nobody is left', async () => {
    mockRules({ approve: { role: 'CUSTOM', subjects: [] } })
    const wrapper = await mountSidebar({ triggers: [periodicTrigger(true)] })

    expect(sectionError(wrapper)).toBe('agentPermissions.chooseSubjects')
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

  test('can change another permission while the first request is pending', async () => {
    mockRules()
    let finishChat
    app.mock.onPut(endpoint + 'chat/').reply(
      () =>
        new Promise((resolve) => {
          finishChat = resolve
        })
    )
    app.mock.onPut(endpoint + 'continue/').reply(200, editor)
    const wrapper = await mountSidebar()
    await openPermissions(wrapper)
    await choose(wrapper, 0, 'fieldPermissionModal.builderTitle')
    await choose(wrapper, 2, 'agentPermissions.EDITOR')

    expect(app.mock.history.put).toHaveLength(2)
    finishChat([200, { role: 'BUILDER', subjects: [] }])
    await flushPromises()
    expect(selectedRoles(wrapper)).toEqual([
      'fieldPermissionModal.builderTitle',
      'agentPermissions.EDITOR',
      'agentPermissions.EDITOR',
    ])
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

  test('starts a custom rule with the first person or team and keeps the picker open across a permissions refresh', async () => {
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
    app.store.commit('workspace/SET_PERMISSIONS', {
      workspaceId: 1,
      permissions: [],
    })
    await flushPromises()

    expect(
      app.mock.history.get.filter(({ url }) => url === endpoint)
    ).toHaveLength(2)
    expect(modal().querySelector('.dropdown__items.hidden')).toBeNull()
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

  test('loads the rules once mounted, never while rendering on the server', async () => {
    vi.spyOn(app.nuxtApp.$licenseHandler, 'hasFeature').mockReturnValue(true)
    const fetches = vi.spyOn(app.store, 'dispatch')
    const sectionType = app
      .getRegistry()
      .get('agentConfigurationSection', 'permissions')
    const Host = defineComponent({
      setup() {
        sectionType.setup({
          agent: { id: 8 },
          workspace: app.store.getters['workspace/get'](1),
        })
        return () => null
      },
    })
    const rulesFetches = () =>
      fetches.mock.calls.filter(
        ([type]) => type === 'agentParticipationRules/fetch'
      )

    await renderToString(createSSRApp(Host))
    expect(rulesFetches()).toEqual([])

    mockRules()
    await app.mount(Host)
    await flushPromises()
    expect(rulesFetches()).toEqual([
      ['agentParticipationRules/fetch', { agentId: 8 }],
    ])
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
