import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import {
  agentData,
  choose,
  completeConfiguration,
  createAgentPage,
  deferredReply,
  destroyAgentPage,
  editInstructions,
  incompleteConfiguration,
  instructions,
  mockAgent,
  mockAvailability,
  mockConfiguration,
  mockRename,
  mockSaves,
  modelDropdown,
  modelError,
  nameInput,
  openSection,
  page,
  providerDropdown,
  savedValues,
  saving,
  unavailableModel,
  useFakeTimers,
  warning,
  withoutConfiguration,
  workspace,
} from './helpers'

describe('Agent configuration', () => {
  let testApp, agent, allowed, mount, leave, update

  beforeEach(async () => {
    ;({ testApp, agent, allowed, mount, leave, update } =
      await createAgentPage())
  })

  afterEach(() => destroyAgentPage(testApp))

  test('toggles the configuration from the header', async () => {
    const wrapper = await mount()
    const toggle = wrapper.get('button[aria-label="agent.configuration"]')
    expect(wrapper.get('.agent-application__header-name').text()).toBe(
      'Support agent'
    )

    await toggle.trigger('click')
    expect(wrapper.find('.agent-configuration').exists()).toBe(false)
    expect(toggle.attributes('aria-expanded')).toBe('false')
    await toggle.trigger('click')

    expect(wrapper.find('.agent-configuration').exists()).toBe(true)
  })

  test('keeps the open form when the Agent changes in the background', async () => {
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    const textarea = instructions(wrapper).element
    const requests = testApp.mock.history.get.length

    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { last_viewed: '2026-10-20T10:00:00Z' },
    })
    await flushPromises()

    expect(instructions(wrapper).element).toBe(textarea)
    expect(testApp.mock.history.get).toHaveLength(requests)
  })

  test('keeps an unsaved edit when the session token is refreshed', async () => {
    const user = { id: 1, username: 'member@example.com' }
    testApp.authenticate(user)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Unsaved instructions')

    testApp.authenticate({ ...user })
    await flushPromises()

    expect(instructions(wrapper).element.value).toBe('Unsaved instructions')
  })

  const remoteUpdate = async (testApp, agent, data = {}) => {
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { readiness: 'ready', ...data },
      viaRealtime: true,
    })
    await flushPromises()
  }

  test('refreshes remote instructions in place without losing focus', async () => {
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    const textarea = instructions(wrapper).element
    textarea.focus()
    mockConfiguration(
      testApp,
      completeConfiguration({ instructions: 'Remote edit' })
    )

    await remoteUpdate(testApp, agent)

    expect(instructions(wrapper).element.value).toBe('Remote edit')
    expect(instructions(wrapper).element).toBe(textarea)
    expect(document.activeElement).toBe(textarea)
    expect(agent).not.toHaveProperty('instructions')
  })

  test('keeps a local draft while refreshing other configuration fields', async () => {
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('My unfinished instructions')
    mockConfiguration(
      testApp,
      completeConfiguration({
        instructions: 'Another user wrote this',
        model_identifier: 'model-two',
      })
    )

    await remoteUpdate(testApp, agent)
    expect(instructions(wrapper).element.value).toBe(
      'My unfinished instructions'
    )
    await wrapper.get('button[aria-label="action.back"]').trigger('click')
    await openSection(wrapper, 'agent.agentSettings')
    expect(modelDropdown(wrapper).get('.dropdown__selected-text').text()).toBe(
      'model-two'
    )
  })

  test('refreshes remote changes received during a save without replacing a newer draft', async () => {
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'First edit')
    await instructions(wrapper).setValue('Still writing')
    mockConfiguration(
      testApp,
      completeConfiguration({
        instructions: 'Remote edit',
        model_identifier: 'model-two',
      })
    )
    await remoteUpdate(testApp, agent)
    patch.resolve(200, completeConfiguration({ instructions: 'First edit' }))
    await flushPromises()

    expect(instructions(wrapper).element.value).toBe('Still writing')
    await wrapper.get('button[aria-label="action.back"]').trigger('click')
    await openSection(wrapper, 'agent.agentSettings')
    expect(modelDropdown(wrapper).get('.dropdown__selected-text').text()).toBe(
      'model-two'
    )
  })

  test('clears the warning as soon as an incomplete draft is fixed', async () => {
    agent.readiness = 'incomplete'
    mockConfiguration(testApp, incompleteConfiguration('instructions'))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    expect(warning(wrapper).exists()).toBe(true)

    await instructions(wrapper).setValue('Ready now')

    expect(warning(wrapper).exists()).toBe(false)
    expect(savedValues(testApp)).toEqual([])
  })

  test('keeps an unfinished name when another member renames the Agent', async () => {
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    await nameInput(wrapper).setValue('My unfinished name')

    await remoteUpdate(testApp, agent, { name: 'Remote name' })

    expect(nameInput(wrapper).element.value).toBe('My unfinished name')
  })

  test('updates the name optimistically and shows saving until the request finishes', async () => {
    const patch = deferredReply()
    mockRename(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    await nameInput(wrapper).setValue('Renamed agent')
    await nameInput(wrapper).trigger('blur')
    await flushPromises()

    expect(agent.name).toBe('Renamed agent')
    expect(saving(wrapper).exists()).toBe(true)
    patch.resolve(200, { ...agentData, name: 'Renamed agent' })
    await flushPromises()
    expect(saving(wrapper).exists()).toBe(false)
  })

  test('does not fetch private configuration for a remote update without access', async () => {
    allowed.value = withoutConfiguration
    const wrapper = await mount()

    await remoteUpdate(testApp, agent, { readiness: 'incomplete' })

    expect(
      testApp.mock.history.get.filter(({ url }) =>
        url.includes('/configuration/')
      )
    ).toEqual([])
    expect(wrapper.find('.agent-configuration').exists()).toBe(false)
    expect(warning(wrapper).exists()).toBe(true)
  })

  test('keeps the focused draft mounted when a background refresh fails', async () => {
    testApp.dontFailOnErrorResponses()
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Still writing')
    const textarea = instructions(wrapper).element
    textarea.focus()
    mockConfiguration(testApp, [500, {}])

    await remoteUpdate(testApp, agent)

    expect(instructions(wrapper).element).toBe(textarea)
    expect(instructions(wrapper).element.value).toBe('Still writing')
    expect(document.activeElement).toBe(textarea)
    expect(warning(wrapper).text()).toContain('agent.readinessLoadError')
  })

  test('keeps a pending model with its provider when another member changes providers', async () => {
    testApp.dontFailOnErrorResponses()
    mockAvailability(testApp, [
      {
        ...workspace,
        ai_features: {
          ai_agent: {
            models: {
              openai: ['model-one', 'model-two'],
              anthropic: ['claude'],
            },
          },
        },
      },
    ])
    mockSaves(
      testApp,
      [500, {}],
      completeConfiguration({ model_identifier: 'model-two' })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    await choose(modelDropdown(wrapper), 'model-two')
    await flushPromises()
    mockConfiguration(
      testApp,
      completeConfiguration({
        provider_type: 'anthropic',
        model_identifier: 'claude',
      })
    )

    await remoteUpdate(testApp, agent)

    expect(
      providerDropdown(wrapper).get('.dropdown__selected-text').text()
    ).toBe('generativeAIModelType.openai')
    expect(modelDropdown(wrapper).get('.dropdown__selected-text').text()).toBe(
      'model-two'
    )
    await wrapper
      .get('.agent-configuration__save-status button')
      .trigger('click')
    await flushPromises()
    expect(savedValues(testApp).at(-1)).toEqual({
      provider_type: 'openai',
      model_identifier: 'model-two',
    })
  })

  test('does not restore an old name from a pending readiness refresh', async () => {
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    const readiness = deferredReply()
    const configuration = deferredReply()
    const rename = deferredReply()
    mockAgent(testApp, readiness.reply)
    mockConfiguration(testApp, configuration.reply)
    mockRename(testApp, rename.reply)
    await testApp.store.dispatch('workspace/forceUpdateGenerativeAIModels', {
      workspaceId: 1,
      generativeAIModelsEnabled: {},
      aiFeatures: {
        ai_agent: {
          models: { openai: ['model-one', 'model-two', 'model-three'] },
        },
      },
    })
    await flushPromises()
    await nameInput(wrapper).setValue('New name')
    await nameInput(wrapper).trigger('blur')
    await flushPromises()

    readiness.resolve(200, agentData)
    await flushPromises()

    expect(agent.name).toBe('New name')
    expect(nameInput(wrapper).element.value).toBe('New name')
    configuration.resolve(200, completeConfiguration())
    rename.resolve(200, { ...agentData, name: 'New name' })
    await flushPromises()
  })

  test('stays on the Agent when a rename already in flight fails during navigation', async () => {
    testApp.dontFailOnErrorResponses()
    const rename = deferredReply()
    mockRename(testApp, rename.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    await nameInput(wrapper).setValue('New name')
    await nameInput(wrapper).trigger('blur')
    await flushPromises()
    const leaving = leave()

    rename.resolve(500, {})

    expect(await leaving).toBe(false)
  })

  test('saves typed text on blur and shows only the header spinner while saving', async () => {
    useFakeTimers()
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Updated instructions')
    await vi.advanceTimersByTimeAsync(1000)
    expect(savedValues(testApp)).toEqual([])

    await instructions(wrapper).trigger('blur')
    await flushPromises()
    expect(saving(wrapper).attributes('aria-label')).toBe('agent.saving')
    expect(wrapper.find('.agent-configuration textarea').exists()).toBe(true)
    patch.resolve(
      200,
      completeConfiguration({ instructions: 'Updated instructions' })
    )
    await flushPromises()

    expect(saving(wrapper).exists()).toBe(false)
    expect(warning(wrapper).exists()).toBe(false)
  })

  test('queues an edit made during a save, even back to the saved value', async () => {
    const first = deferredReply()
    mockSaves(testApp, first.reply, completeConfiguration())
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Changed instructions')
    await editInstructions(wrapper, 'Be helpful.')

    first.resolve(
      200,
      completeConfiguration({ instructions: 'Changed instructions' })
    )
    await flushPromises()

    expect(savedValues(testApp)).toEqual([
      { instructions: 'Changed instructions' },
      { instructions: 'Be helpful.' },
    ])
    expect(instructions(wrapper).element.value).toBe('Be helpful.')
  })

  test('saves pending edits before leaving the Agent', async () => {
    const first = deferredReply()
    const second = deferredReply()
    mockSaves(testApp, first.reply, second.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Changed instructions')
    await instructions(wrapper).setValue('Be helpful.')
    const completed = vi.fn()
    const leaving = leave().then((result) => completed(result) || result)

    first.resolve(
      200,
      completeConfiguration({ instructions: 'Changed instructions' })
    )
    await flushPromises()
    expect(completed).not.toHaveBeenCalled()
    second.resolve(200, completeConfiguration())

    expect(await leaving).toBe(true)
    expect(savedValues(testApp)).toHaveLength(2)
  })

  test('stays on the Agent with the draft when saving before leaving fails', async () => {
    testApp.dontFailOnErrorResponses()
    mockSaves(testApp, [500, {}])
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Unsaved instructions')

    expect(await leave()).toBe(false)
    await flushPromises()

    expect(instructions(wrapper).element.value).toBe('Unsaved instructions')
    expect(wrapper.text()).toContain('agent.configurationSaveError')
  })

  test('keeps the current Agent selected when saving before switching Agents fails', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    mockSaves(testApp, [500, {}])
    const next = await testApp.store.dispatch('application/forceCreate', {
      ...agentData,
      id: 11,
    })
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Unsaved instructions')
    await testApp.store.dispatch('application/select', next)

    const switched = await update(
      { params: { agentId: '11' } },
      { params: { agentId: '10' } }
    )

    expect(switched).toBe(false)
    expect(testApp.store.getters['application/getSelected'].id).toBe(10)
  })

  test('keeps a failed model save without a required error until retry succeeds', async () => {
    testApp.dontFailOnErrorResponses()
    mockConfiguration(testApp, incompleteConfiguration('model_identifier'))
    mockSaves(testApp, [500, {}], completeConfiguration())
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    await choose(modelDropdown(wrapper), 'model-one')
    await flushPromises()

    expect(modelError(wrapper).exists()).toBe(false)
    expect(wrapper.text()).toContain('agent.configurationSaveError')
    await wrapper
      .get('.agent-configuration__save-status button')
      .trigger('click')
    await flushPromises()

    expect(wrapper.find('.agent-configuration__save-status').exists()).toBe(
      false
    )
    expect(warning(wrapper).exists()).toBe(false)
  })

  test('clears the model when the provider changes and then requires a model', async () => {
    mockAvailability(testApp, [
      {
        ...workspace,
        ai_features: {
          ai_agent: {
            models: { openai: ['model-one'], anthropic: ['claude'] },
          },
        },
      },
    ])
    mockSaves(testApp, {
      ...incompleteConfiguration('model_identifier'),
      provider_type: 'anthropic',
    })
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')

    await choose(providerDropdown(wrapper), 'anthropic')
    await flushPromises()

    expect(savedValues(testApp)).toEqual([
      { provider_type: 'anthropic', model_identifier: null },
    ])
    expect(modelError(wrapper).text()).toBe('error.requiredField')
  })

  test('keeps the model when the selected provider is chosen again', async () => {
    mockSaves(testApp, completeConfiguration({ model_identifier: null }))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')

    await choose(providerDropdown(wrapper), 'openai')
    await flushPromises()

    expect(savedValues(testApp)).toEqual([])
  })

  test('ties an unavailable model error to the selection it was returned for', async () => {
    mockConfiguration(testApp, unavailableModel('retired-model'))
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    const model = modelDropdown(wrapper)
    expect(model.get('.dropdown__selected-text').text()).toBe('retired-model')
    expect(modelError(wrapper).text()).toBe('agent.modelUnavailable')

    await choose(model, 'model-two')
    expect(modelError(wrapper).exists()).toBe(false)
    await flushPromises()
    patch.resolve(200, unavailableModel('model-two'))
    await flushPromises()

    expect(modelError(wrapper).text()).toBe('agent.modelUnavailable')
  })

  test('does not restore an older required error over a newer queued selection', async () => {
    const incomplete = incompleteConfiguration('model_identifier')
    mockConfiguration(testApp, incomplete)
    const first = deferredReply()
    mockSaves(
      testApp,
      first.reply,
      completeConfiguration({ model_identifier: 'model-two' })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Updated instructions')
    await wrapper
      .get('.agent-configuration__header button[aria-label="action.back"]')
      .trigger('click')
    await openSection(wrapper, 'agent.agentSettings')
    await choose(modelDropdown(wrapper), 'model-two')
    expect(modelError(wrapper).exists()).toBe(false)

    first.resolve(200, { ...incomplete, instructions: 'Updated instructions' })
    await flushPromises()
    expect(modelError(wrapper).exists()).toBe(false)
    await flushPromises()

    expect(savedValues(testApp)[1]).toEqual({ model_identifier: 'model-two' })
    expect(modelError(wrapper).exists()).toBe(false)
  })

  test.each([
    ['instructions', 'agent.instructions', '.agent-configuration textarea'],
    ['model_identifier', 'agent.model', '.agent-configuration .dropdown'],
  ])(
    'opens the configuration on the invalid %s field from its warning',
    async (field, label, selector) => {
      mockConfiguration(testApp, incompleteConfiguration(field))
      const wrapper = await mount()
      await wrapper
        .get('.agent-configuration__header button[aria-label="action.close"]')
        .trigger('click')

      await wrapper
        .findAll('.agent-chat__warning-link')
        .find((button) => button.text() === label)
        .trigger('click')
      await flushPromises()

      const target = wrapper.findAll(selector).at(-1).element
      expect(target.contains(document.activeElement)).toBe(true)
    }
  )

  test('flags the section that holds a missing setting', async () => {
    mockConfiguration(testApp, incompleteConfiguration('model_identifier'))
    const wrapper = await mount()

    const [instructionsSection, , settingsSection] = wrapper.findAll(
      '.menu-list__item-button'
    )

    expect(instructionsSection.find('.icon--error').exists()).toBe(false)
    expect(settingsSection.get('.icon--error').attributes('aria-label')).toBe(
      'agent.fieldError'
    )
  })

  test('runs as a chosen identity or with no workspace access', async () => {
    testApp.mock.onGet('/subjects/').reply(
      200,
      page([
        {
          id: 'core.Agent:7',
          subject_id: 7,
          subject_type: 'core.Agent',
          name: 'Investor',
        },
      ])
    )
    const investor = { type: 'core.Agent', id: 7, name: 'Investor' }
    mockSaves(
      testApp,
      completeConfiguration({ run_as: { ...investor, trashed: false } }),
      completeConfiguration({ run_as: null })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    const body = () => wrapper.get('.agent-configuration__body')
    const select = async (name) => {
      await body().get('.dropdown__selected').trigger('click')
      await flushPromises()
      await body()
        .findAll('.select__item-link')
        .find((item) => item.text().includes(name))
        .trigger('click')
      await flushPromises()
    }

    await select('Investor')
    expect(body().text()).toContain('agent.runAsHelper')
    await select('agent.noWorkspaceAccess')

    expect(savedValues(testApp)).toEqual([
      { run_as_subject_type: 'core.Agent', run_as_subject_id: 7 },
      { run_as_subject_type: null, run_as_subject_id: null },
    ])
    expect(body().text()).toContain('agent.noWorkspaceAccessHelper')
  })

  const investor = {
    type: 'core.Agent',
    id: 7,
    name: 'Investor',
    trashed: false,
  }

  test.each([
    ['assigns an identity', null, investor, 'Investor'],
    ['clears the identity', investor, null, 'agent.noWorkspaceAccess'],
    [
      'changes the identity',
      investor,
      { ...investor, id: 8, name: 'Support' },
      'Support',
    ],
    [
      'renames the identity',
      investor,
      { ...investor, name: 'Renamed investor' },
      'Renamed investor',
    ],
  ])(
    'refreshes the run-as label when another editor %s',
    async (_, previous, next, expectedLabel) => {
      useFakeTimers()
      testApp.mock.onGet('/subjects/').reply(200, page([]))
      mockConfiguration(testApp, completeConfiguration({ run_as: previous }))
      const wrapper = await mount()
      await openSection(wrapper, 'agent.workspaceAccess')
      await wrapper
        .get('.agent-configuration .dropdown__selected')
        .trigger('click')
      const search = wrapper.get('.agent-configuration .select__search-input')
      await search.setValue('Inv')
      search.element.focus()
      mockConfiguration(testApp, completeConfiguration({ run_as: next }))

      await remoteUpdate(testApp, agent)

      expect(
        wrapper.get('.agent-configuration .dropdown__selected-text').text()
      ).toBe(expectedLabel)
      expect(
        wrapper.get('.agent-configuration .control__helper-text').text()
      ).toContain(next ? 'agent.runAsHelper' : 'agent.noWorkspaceAccessHelper')
      expect(
        wrapper.get('.agent-configuration .dropdown__items').classes()
      ).not.toContain('hidden')
      expect(search.element.value).toBe('Inv')
      expect(document.activeElement).toBe(search.element)
      expect(savedValues(testApp)).toEqual([])
    }
  )

  test('allows workspace tools with presets or one by one', async () => {
    const withTools = (tools) =>
      completeConfiguration({
        tools,
        available_tools: [
          { name: 'list_tables', group: 'database', changes_data: false },
          { name: 'create_rows', group: 'database', changes_data: true },
          { name: 'delete_rows', group: 'database', changes_data: true },
        ],
      })
    const everything = ['list_tables', 'create_rows', 'delete_rows']
    mockConfiguration(testApp, withTools(['list_tables']))
    mockSaves(
      testApp,
      withTools(everything),
      withTools(['list_tables', 'create_rows']),
      withTools([])
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await flushPromises()
    const tools = () => wrapper.get('.agent-workspace-tools')
    const inModal = (selector, text) =>
      [...document.body.querySelectorAll(selector)].find((element) =>
        element.textContent.includes(text)
      )
    expect(tools().get('.segment-control__button--active').text()).toBe(
      'agent.toolsReadOnly'
    )

    await tools()
      .findAll('.segment-control__button')
      .find((button) => button.text() === 'agent.toolsEverything')
      .trigger('click')
    await flushPromises()
    await tools().get('.agent-workspace-tools__group').trigger('click')
    await flushPromises()
    inModal('.agent-tool-permissions__tool', 'agent.toolDeleteRows')
      .querySelector('input')
      .click()
    inModal(
      '.agent-tool-permissions__actions button',
      'agent.toolsDone'
    ).click()
    await flushPromises()
    await tools().get('.switch').trigger('click')
    await flushPromises()

    expect(savedValues(testApp)).toEqual([
      { tools: everything },
      { tools: ['list_tables', 'create_rows'] },
      { tools: [] },
    ])
    expect(wrapper.find('.agent-workspace-tools__group').exists()).toBe(false)
  })

  test('renames the Agent through the application with the trimmed name', async () => {
    mockRename(testApp, { ...agentData, name: 'Support' })
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')

    await nameInput(wrapper).setValue('  Support  ')
    await nameInput(wrapper).trigger('blur')
    await flushPromises()

    expect(
      testApp.mock.history.patch.map(({ url, data }) => [url, JSON.parse(data)])
    ).toEqual([['/applications/10/', { name: 'Support' }]])
    expect(nameInput(wrapper).element.value).toBe('Support')
    expect(wrapper.get('.agent-application__header-name').text()).toBe(
      'Support'
    )
  })

  test('restores the saved name instead of saving a blank one', async () => {
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')

    await nameInput(wrapper).setValue(' ')
    await nameInput(wrapper).trigger('blur')
    await flushPromises()

    expect(nameInput(wrapper).element.value).toBe('Support agent')
    expect(testApp.mock.history.patch).toEqual([])
  })

  test.each([
    ['cannot read', withoutConfiguration],
    [
      'can read but not edit',
      (operation) => operation !== 'application.update',
    ],
  ])(
    'asks members who %s the configuration to contact an administrator',
    async (_, permission) => {
      allowed.value = permission
      agent.readiness = 'incomplete'
      mockConfiguration(testApp, incompleteConfiguration('instructions'))
      const wrapper = await mount()

      expect(wrapper.text()).toContain('agent.configurationPermissionRequired')
      expect(wrapper.find('.agent-chat__warning-link').exists()).toBe(false)
    }
  )

  test.each(['ready', 'incomplete', 'unavailable'])(
    'uses the serialized %s readiness without another application request',
    async (readiness) => {
      allowed.value = withoutConfiguration
      agent.readiness = readiness
      const wrapper = await mount()

      expect(warning(wrapper).exists()).toBe(readiness !== 'ready')
      expect(testApp.mock.history.get.map(({ url }) => url)).toEqual([
        '/agent/10/conversations/',
      ])
    }
  )

  test('never shows the configuration after read access is revoked during a save', async () => {
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'PRIVATE')

    allowed.value = withoutConfiguration
    await flushPromises()
    mockAgent(testApp, { ...agentData, readiness: 'incomplete' })
    patch.resolve(200, completeConfiguration({ instructions: 'PRIVATE' }))
    await flushPromises()

    expect(wrapper.find('.agent-configuration').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('PRIVATE')
    expect(testApp.store.getters['application/get'](10)).not.toHaveProperty(
      'instructions'
    )
    expect(wrapper.text()).toContain('agent.configurationPermissionRequired')
  })

  test('refreshes readiness when model availability changes', async () => {
    allowed.value = withoutConfiguration
    const wrapper = await mount()
    mockAgent(testApp, { ...agentData, readiness: 'unavailable' })

    await testApp.store.dispatch('workspace/forceUpdateGenerativeAIModels', {
      workspaceId: 1,
      generativeAIModelsEnabled: {},
      aiFeatures: { ai_agent: { models: {} } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('agent.configurationPermissionRequired')
  })

  test('warns when refreshing the readiness fails and retries it', async () => {
    allowed.value = withoutConfiguration
    testApp.dontFailOnErrorResponses()
    const wrapper = await mount()
    mockAgent(testApp, [500, {}], agentData)

    await testApp.store.dispatch('workspace/forceUpdateGenerativeAIModels', {
      workspaceId: 1,
      generativeAIModelsEnabled: {},
      aiFeatures: { ai_agent: { models: {} } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('agent.readinessLoadError')

    await wrapper.get('.agent-chat__warning button').trigger('click')
    await flushPromises()

    expect(warning(wrapper).exists()).toBe(false)
    expect(
      testApp.mock.history.get.some(({ url }) => url === '/agent/10/')
    ).toBe(false)
  })

  test('shows a failed configuration load in the sidebar until retry', async () => {
    testApp.dontFailOnErrorResponses()
    mockConfiguration(testApp, [500, {}], completeConfiguration())
    const wrapper = await mount()
    expect(wrapper.text()).toContain('agent.configurationLoadError')
    expect(wrapper.findAll('.menu-list__item-button')).toHaveLength(0)

    await wrapper
      .get('.agent-configuration__body .alert button')
      .trigger('click')
    await flushPromises()

    expect(wrapper.findAll('.menu-list__item-button')).toHaveLength(3)
  })

  test('warns when model availability cannot be loaded until retry', async () => {
    testApp.dontFailOnErrorResponses()
    mockAvailability(testApp, [500, {}], [workspace])
    const wrapper = await mount()
    expect(wrapper.text()).toContain('agent.readinessLoadError')

    await wrapper.get('.agent-chat__warning button').trigger('click')
    await flushPromises()

    expect(warning(wrapper).exists()).toBe(false)
  })
})
