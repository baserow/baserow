import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import AgentCreateModal from '@baserow/modules/agent/components/AgentCreateModal'
import AgentCreateReviewStep from '@baserow/modules/agent/components/AgentCreateReviewStep'
import { choose, page, workspace as workspaceData } from './helpers'

const tools = [
  { name: 'list_tables', group: 'database', changes_data: false },
  { name: 'create_rows', group: 'database', changes_data: true },
]

describe('AgentCreateModal', () => {
  let testApp, workspace, agentType

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      ...clone(workspaceData),
      ai_features: {
        ai_agent: { models: { openai: ['model-one'], ollama: ['llama'] } },
      },
    })
    workspace = testApp.store.getters['workspace/get'](workspaceData.id)
    agentType = testApp.getRegistry().get('application', 'agent')
    testApp.mock.onGet('/identities/workspace/1/').reply(200, page([]))
    testApp.mock.onGet('/agent/tools/workspace/1/').reply(200, tools)
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  async function open({ identities = false } = {}) {
    // Without the identities flag the setup starts with no workspace access.
    const app = Object.create(testApp.nuxtApp)
    Object.defineProperty(app, '$featureFlagIsEnabled', {
      value: () => identities,
    })
    Object.defineProperty(app, '$hasPermission', { value: () => true })
    const wrapper = await testApp.mount(AgentCreateModal, {
      props: { applicationType: agentType, workspace },
      global: { plugins: [{ install: (vueApp) => (vueApp.$nuxt = app) }] },
    })
    wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  const button = (wrapper, label) =>
    wrapper.findAll('button').find((item) => item.text() === label)
  const nameInput = (wrapper) => wrapper.get('.agent-create__body input')
  const textarea = (wrapper) => wrapper.get('.agent-create__body textarea')
  const title = (wrapper) => wrapper.get('.agent-create__title').text()
  const dropdown = (wrapper, label) =>
    wrapper
      .findAll('.agent-create__body .control')
      .find((control) => control.get('.control__label').text().includes(label))
      .get('.dropdown')
  const selected = (wrapper, label) =>
    dropdown(wrapper, label).get('.dropdown__selected').text()
  const setup = (wrapper) =>
    wrapper.findComponent(AgentCreateReviewStep).props('modelValue')

  async function next(wrapper, times = 1) {
    for (let step = 0; step < times; step++) {
      await button(wrapper, 'agent.setupContinue').trigger('click')
      await flushPromises()
    }
  }

  const back = (wrapper) =>
    wrapper.get('button[aria-label="action.back"]').trigger('click')

  async function chooseCustomTools(wrapper, label) {
    await choose(
      dropdown(wrapper, 'agent.setupPermissions'),
      'agent.setupPermissionsCustom'
    )
    await wrapper
      .findAll('.agent-tool-permissions__ask-first input')[1]
      .setValue(false)
    await wrapper
      .findAll('.agent-tool-permissions__actions button')
      .find((item) => item.text() === label)
      .trigger('click')
    // A modal closes on a timer that flushPromises doesn't wait for.
    await new Promise((resolve) => setTimeout(resolve))
  }

  test('continues once named, and a suggestion fills the setup', async () => {
    const wrapper = await open()

    await nameInput(wrapper).setValue(' ')
    expect(
      button(wrapper, 'agent.setupContinue').attributes('disabled')
    ).toBeDefined()

    await wrapper.findAll('.agent-create__suggestion')[3].trigger('click')

    expect(nameInput(wrapper).element.value).toBe(
      'agent.setupSuggestionSummaryName'
    )
    expect(textarea(wrapper).element.value).toBe(
      'agent.setupSuggestionSummaryInstructions'
    )

    await next(wrapper)

    expect(setup(wrapper)).toMatchObject({
      start: 'schedule',
      permissions: 'read',
    })
    expect(wrapper.get('.agent-create__schedule-name').text()).toBe(
      'serviceType.corePeriodicNameWeek'
    )
  })

  test('keeps the values of all three screens when going back', async () => {
    const wrapper = await open()
    await nameInput(wrapper).setValue('Deal scout')
    await textarea(wrapper).setValue('Find companies.')

    await next(wrapper)
    expect(title(wrapper)).toBe('agent.setupReviewTitle')
    expect(textarea(wrapper).element.value).toBe('Find companies.')
    await textarea(wrapper).setValue('Find more companies.')
    await next(wrapper)
    expect(title(wrapper)).toBe('agent.setupModelTitle')
    expect(selected(wrapper, 'agent.model')).toBe('model-one')
    await choose(
      dropdown(wrapper, 'agent.reasoningEffort'),
      'agent.reasoningEffortHigh'
    )

    await back(wrapper)
    expect(title(wrapper)).toBe('agent.setupReviewTitle')
    await next(wrapper)
    expect(selected(wrapper, 'agent.reasoningEffort')).toBe(
      'agent.reasoningEffortHigh'
    )
    await back(wrapper)
    await back(wrapper)

    expect(title(wrapper)).toBe('agent.createApplication')
    expect(nameInput(wrapper).element.value).toBe('Deal scout')
    expect(textarea(wrapper).element.value).toBe('Find more companies.')
  })

  test('sets custom permissions only when the tool modal is done', async () => {
    const wrapper = await open({ identities: true })
    await next(wrapper)

    await chooseCustomTools(wrapper, 'action.cancel')
    expect(selected(wrapper, 'agent.setupPermissions')).toBe(
      'agent.setupPermissionsAsk'
    )
    expect(setup(wrapper).customTools).toBeNull()

    await chooseCustomTools(wrapper, 'agent.toolsDone')

    expect(title(wrapper)).toBe('agent.setupReviewTitle')
    expect(selected(wrapper, 'agent.setupPermissions')).toBe(
      'agent.setupPermissionsCustomSummary - 0'
    )
    expect(setup(wrapper)).toMatchObject({
      permissions: 'custom',
      customTools: {
        allowed_tools: ['list_tables', 'create_rows'],
        ask_first_tools: [],
      },
    })
  })

  test('acts as the identity created from the dropdown', async () => {
    testApp.mock
      .onPost('/identities/workspace/1/')
      .reply(200, { id: 7, name: 'Investor', workspace_id: 1 })
    const wrapper = await open({ identities: true })
    await next(wrapper)

    await choose(
      dropdown(wrapper, 'agent.setupActsAs'),
      'agent.runAsCreateIdentity'
    )
    await flushPromises()
    expect(setup(wrapper).actsAs.kind).toBe('new')
    await wrapper.get('.modal__box .modal__box input').setValue('Investor')
    await wrapper.get('.modal__box .modal__box form').trigger('submit')
    await flushPromises()

    expect(title(wrapper)).toBe('agent.setupReviewTitle')
    expect(setup(wrapper).actsAs).toEqual({
      kind: 'existing',
      id: 7,
      name: 'Investor',
    })
  })

  test('needs a model once a provider is chosen', async () => {
    const wrapper = await open()
    await next(wrapper, 2)
    const create = () =>
      button(wrapper, 'agent.createApplication').attributes('disabled')
    expect(create()).toBeUndefined()

    await choose(dropdown(wrapper, 'agent.provider'), 'ollama')
    expect(create()).toBeDefined()

    await choose(dropdown(wrapper, 'agent.model'), 'llama')
    expect(create()).toBeUndefined()
  })

  test('stays open with the error when the agent is not created', async () => {
    testApp.dontFailOnErrorResponses()
    const select = vi.spyOn(agentType, 'select').mockResolvedValue(true)
    testApp.mock.onPost('/applications/workspace/1/').reply(400, {
      error: 'ERROR_REQUEST_BODY_VALIDATION',
      detail: {},
    })
    const wrapper = await open()
    await next(wrapper, 2)

    await button(wrapper, 'agent.createApplication').trigger('click')
    await flushPromises()

    expect(wrapper.find('.agent-create .alert').exists()).toBe(true)
    expect(wrapper.emitted('created')).toBeUndefined()
    expect(select).not.toHaveBeenCalled()
    expect(
      button(wrapper, 'agent.createApplication').attributes('disabled')
    ).toBeUndefined()
  })

  test('opens the agent and warns about what was not applied', async () => {
    testApp.dontFailOnErrorResponses()
    const select = vi.spyOn(agentType, 'select').mockResolvedValue(true)
    testApp.mock.onPost('/applications/workspace/1/').reply(200, {
      id: 10,
      name: 'Deal scout',
      type: 'agent',
      workspace: { id: 1 },
    })
    testApp.mock.onGet('/agent/10/configuration/').reply(200, {
      available_tools: [],
      web_search_available: false,
      available_action_types: [],
    })
    testApp.mock.onPatch('/agent/10/configuration/').reply(500)
    const wrapper = await open()
    await nameInput(wrapper).setValue('Deal scout')
    await textarea(wrapper).setValue('Find companies.')
    await next(wrapper, 2)

    await button(wrapper, 'agent.createApplication').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('created')[0][0].id).toBe(10)
    expect(select).toHaveBeenCalledWith(expect.objectContaining({ id: 10 }))
    expect(wrapper.find('.agent-create').exists()).toBe(false)
    expect(testApp.store.state.toast.items).toEqual([
      expect.objectContaining({
        type: 'warning',
        title: 'agent.setupPartialTitle',
      }),
    ])
  })
})
