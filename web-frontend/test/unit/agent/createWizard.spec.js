import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import AgentCreateModal from '@baserow/modules/agent/components/AgentCreateModal'
import { page, workspace as workspaceData } from './helpers'

describe('AgentCreateModal', () => {
  let testApp, workspace, agentType

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', clone(workspaceData))
    workspace = testApp.store.getters['workspace/get'](workspaceData.id)
    agentType = testApp.getRegistry().get('application', 'agent')
    testApp.mock.onGet('/identities/workspace/1/').reply(200, page([]))
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    await testApp.afterEach()
  })

  async function open() {
    // Without the identities flag the setup starts with no workspace access.
    const app = Object.create(testApp.nuxtApp)
    Object.defineProperty(app, '$featureFlagIsEnabled', { value: () => false })
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

  test('continues once named, and a suggestion fills both fields', async () => {
    const wrapper = await open()

    await nameInput(wrapper).setValue(' ')
    expect(
      button(wrapper, 'agent.setupContinue').attributes('disabled')
    ).toBeDefined()

    await wrapper.findAll('.agent-create__suggestion')[0].trigger('click')

    expect(nameInput(wrapper).element.value).toBe(
      'agent.setupSuggestionInvestName'
    )
    expect(textarea(wrapper).element.value).toBe(
      'agent.setupSuggestionInvestInstructions'
    )
    expect(
      button(wrapper, 'agent.setupContinue').attributes('disabled')
    ).toBeUndefined()
  })

  test('keeps what was typed when going back', async () => {
    const wrapper = await open()
    await nameInput(wrapper).setValue('Deal scout')
    await textarea(wrapper).setValue('Find companies.')

    await button(wrapper, 'agent.setupContinue').trigger('click')
    await flushPromises()
    expect(title(wrapper)).toBe('agent.setupReviewTitle')
    expect(textarea(wrapper).element.value).toBe('Find companies.')
    await textarea(wrapper).setValue('Find more companies.')

    await wrapper.get('button[aria-label="action.back"]').trigger('click')

    expect(title(wrapper)).toBe('agent.createApplication')
    expect(nameInput(wrapper).element.value).toBe('Deal scout')
    expect(textarea(wrapper).element.value).toBe('Find more companies.')
  })

  test('stays open with the error when the agent is not created', async () => {
    testApp.dontFailOnErrorResponses()
    const select = vi.spyOn(agentType, 'select').mockResolvedValue(true)
    testApp.mock.onPost('/applications/workspace/1/').reply(400, {
      error: 'ERROR_REQUEST_BODY_VALIDATION',
      detail: {},
    })
    const wrapper = await open()
    await button(wrapper, 'agent.setupContinue').trigger('click')
    await flushPromises()

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
    await button(wrapper, 'agent.setupContinue').trigger('click')
    await flushPromises()

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
