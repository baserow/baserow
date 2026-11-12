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
  reasoningEffortDropdown,
  reasoningEffortWarning,
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

  const invalidateRunAs = (selected = true, agentIds = [agent.id]) =>
    testApp.nuxtApp.$realtime._dispatchEvent({
      type: 'agent_run_as_updated',
      agent_ids: agentIds,
      selected_agent_ids: selected ? [agent.id] : [],
    })

  const pickRunAs = async (wrapper, name) => {
    await wrapper
      .get('.agent-configuration .dropdown__selected')
      .trigger('click')
    await flushPromises()
    await wrapper
      .findAll('.agent-configuration .select__item-link')
      .find((item) => item.text().includes(name))
      .trigger('click')
    await flushPromises()
  }

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
    [
      'instructions',
      'agent.instructions',
      (wrapper) => wrapper.findAll('.agent-configuration textarea').at(-1),
    ],
    ['model_identifier', 'agent.model', modelDropdown],
  ])(
    'opens the configuration on the invalid %s field from its warning',
    async (field, label, findTarget) => {
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

      const target = findTarget(wrapper).element
      expect(target.contains(document.activeElement)).toBe(true)
    }
  )

  test('flags the section that holds a missing setting', async () => {
    mockConfiguration(testApp, incompleteConfiguration('model_identifier'))
    const wrapper = await mount()

    const [instructionsSection, , , settingsSection] = wrapper.findAll(
      '.menu-list__item-button'
    )

    expect(instructionsSection.find('.icon--error').exists()).toBe(false)
    expect(settingsSection.get('.icon--error').attributes('aria-label')).toBe(
      'agent.fieldError'
    )
  })

  test('runs as a chosen identity or with no workspace access', async () => {
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
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

  const workspaceAccessRow = (wrapper) =>
    wrapper
      .findAll('.menu-list__item-button')
      .find((button) => button.text().includes('agent.workspaceAccess'))

  test.each([
    ['trashed', { ...investor, trashed: true }, true],
    ['active', investor, false],
    ['unset', null, false],
  ])(
    'flags workspace access without opening it when the identity is %s',
    async (_, identity, hasError) => {
      mockConfiguration(testApp, completeConfiguration({ run_as: identity }))
      const wrapper = await mount()
      const error = workspaceAccessRow(wrapper).find('.icon--error')

      expect(error.exists()).toBe(hasError)
      if (hasError) {
        expect(error.attributes('aria-label')).toBe('agent.runAsTrashed')
      }
      expect(wrapper.find('.agent-configuration__body').exists()).toBe(false)
      expect(warning(wrapper).exists()).toBe(false)
      expect(wrapper.find('.agent-chat__composer').exists()).toBe(true)
    }
  )

  test('updates the collapsed workspace access error when the identity is deleted and restored', async () => {
    useFakeTimers()
    mockConfiguration(testApp, completeConfiguration({ run_as: investor }))
    const wrapper = await mount()
    const error = () => workspaceAccessRow(wrapper).find('.icon--error')
    const requests = testApp.mock.history.get.length

    await testApp.store.dispatch('agent/forceDelete', {
      workspaceId: 2,
      agentId: investor.id,
    })
    await flushPromises()
    expect(testApp.mock.history.get).toHaveLength(requests)

    mockConfiguration(
      testApp,
      completeConfiguration({ run_as: { ...investor, trashed: true } })
    )
    await invalidateRunAs()
    await vi.advanceTimersByTimeAsync(100)
    await flushPromises()

    expect(error().attributes('aria-label')).toBe('agent.runAsTrashed')
    expect(wrapper.find('.agent-configuration__body').exists()).toBe(false)
    expect(warning(wrapper).exists()).toBe(false)

    mockConfiguration(testApp, completeConfiguration({ run_as: investor }))
    await invalidateRunAs()
    await vi.advanceTimersByTimeAsync(100)
    await flushPromises()

    expect(error().exists()).toBe(false)
    expect(savedValues(testApp)).toEqual([])
  })

  test.each([
    [
      'a replacement identity',
      { ...investor, id: 8, name: 'Support' },
      'Support',
    ],
    ['no workspace access', null, 'agent.noWorkspaceAccess'],
  ])(
    'clears the workspace access error after choosing %s',
    async (_, identity, label) => {
      mockConfiguration(
        testApp,
        completeConfiguration({ run_as: { ...investor, trashed: true } })
      )
      testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
        200,
        page([
          {
            id: 'core.Agent:8',
            subject_id: 8,
            subject_type: 'core.Agent',
            name: 'Support',
          },
        ])
      )
      mockSaves(testApp, completeConfiguration({ run_as: identity }))
      const wrapper = await mount()
      expect(workspaceAccessRow(wrapper).find('.icon--error').exists()).toBe(
        true
      )

      await openSection(wrapper, 'agent.workspaceAccess')
      expect(wrapper.get('.control__messages').text()).toContain(
        'agent.runAsTrashed'
      )
      await wrapper
        .get('.agent-configuration .dropdown__selected')
        .trigger('click')
      await flushPromises()
      await wrapper
        .findAll('.agent-configuration .select__item-link')
        .find((item) => item.text().includes(label))
        .trigger('click')
      await flushPromises()
      await wrapper.get('button[aria-label="action.back"]').trigger('click')

      expect(workspaceAccessRow(wrapper).find('.icon--error').exists()).toBe(
        false
      )
      expect(savedValues(testApp)).toEqual([
        {
          run_as_subject_type: identity?.type ?? null,
          run_as_subject_id: identity?.id ?? null,
        },
      ])
    }
  )

  test('shows a missing identity distinctly and can clear it directly', async () => {
    const missing = { ...investor, name: null, status: 'missing' }
    mockConfiguration(testApp, completeConfiguration({ run_as: missing }))
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(200, page([]))
    mockSaves(testApp, completeConfiguration({ run_as: null }))
    const wrapper = await mount()
    expect(
      workspaceAccessRow(wrapper).get('.icon--error').attributes('aria-label')
    ).toBe('agent.runAsMissing')
    await openSection(wrapper, 'agent.workspaceAccess')
    expect(wrapper.get('.dropdown__selected-text').text()).toBe(
      'agent.runAsMissingLabel'
    )
    expect(wrapper.get('.agent-configuration .dropdown').classes()).toContain(
      'dropdown--error'
    )
    expect(wrapper.find('.control__helper-text').exists()).toBe(false)
    await pickRunAs(wrapper, 'agent.noWorkspaceAccess')
    expect(savedValues(testApp)).toEqual([
      { run_as_subject_type: null, run_as_subject_id: null },
    ])
    expect(wrapper.get('.control__helper-text').text()).toBe(
      'agent.noWorkspaceAccessHelper'
    )
  })

  test('does not fetch identities for a readonly field and revalidates after edit permission is granted', async () => {
    allowed.value = (operation) => operation !== 'application.update'
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(200, page([]))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    const requests = () =>
      testApp.mock.history.get.filter(({ url }) =>
        url.includes('/run-as-subjects/')
      )
    expect(requests()).toHaveLength(0)
    allowed.value = () => true
    await flushPromises()
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(requests()).toHaveLength(1)
    expect(requests()[0].headers['X-Baserow-Realtime-Recovery']).toBe('true')
  })

  test.each([
    [1, false],
    [1, true],
    [50, false],
    [50, true],
  ])(
    'bounds refresh requests for a batch of %s applications with selected identity changed=%s',
    async (applicationCount, selected) => {
      useFakeTimers()
      const agentIds = [agent.id]
      for (let offset = 1; offset < applicationCount; offset++) {
        const id = agent.id + offset
        await testApp.store.dispatch('application/forceCreate', {
          ...agentData,
          id,
        })
        agentIds.push(id)
      }
      mockConfiguration(testApp, completeConfiguration({ run_as: investor }))
      testApp.mock.onGet('/agent/10/run-as-subjects/').reply(200, page([]))
      const wrapper = await mount()
      await openSection(wrapper, 'agent.workspaceAccess')
      await wrapper.get('.dropdown__selected').trigger('click')
      await flushPromises()
      testApp.mock.resetHistory()

      await invalidateRunAs(selected, agentIds)
      await vi.advanceTimersByTimeAsync(500)
      await flushPromises()

      expect(testApp.mock.history.get.map(({ url }) => url).sort()).toEqual(
        selected
          ? ['/agent/10/configuration/', '/agent/10/run-as-subjects/']
          : ['/agent/10/run-as-subjects/']
      )
    }
  )

  test('refreshes choices on opening and coalesces candidate events without fetching configuration or losing search and focus', async () => {
    useFakeTimers()
    const subjects = () =>
      testApp.mock.history.get.filter(({ url }) =>
        url.includes('/run-as-subjects/')
      )
    const configurations = () =>
      testApp.mock.history.get.filter(({ url }) =>
        url.includes('/configuration/')
      )
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
      200,
      page([
        {
          id: 'core.Agent:7',
          subject_type: 'core.Agent',
          subject_id: 7,
          name: 'Investor',
        },
      ])
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    const search = wrapper.get('.select__search-input')
    await search.setValue('Inv')
    await vi.advanceTimersByTimeAsync(400)
    search.element.focus()
    const configCount = configurations().length
    const subjectCount = subjects().length
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
      200,
      page([
        {
          id: 'core.Agent:8',
          subject_type: 'core.Agent',
          subject_id: 8,
          name: 'Investor replacement',
        },
      ])
    )
    for (let event = 0; event < 5; event++) {
      await invalidateRunAs(false)
      await vi.advanceTimersByTimeAsync(10)
    }
    await vi.advanceTimersByTimeAsync(100)
    await flushPromises()
    expect(configurations()).toHaveLength(configCount)
    expect(subjects()).toHaveLength(subjectCount + 1)
    expect(subjects().at(-1).params.search).toBe('Inv')
    expect(wrapper.get('.select__items').text()).toContain(
      'Investor replacement'
    )
    expect(search.element.value).toBe('Inv')
    expect(document.activeElement).toBe(search.element)
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await wrapper.get('.dropdown__selected').trigger('click')
    await flushPromises()
    expect(subjects()).toHaveLength(subjectCount + 2)
  })

  test('coalesces selected identity events and preserves primary-read recovery across an in-flight save', async () => {
    useFakeTimers()
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Changed')
    const requests = () =>
      testApp.mock.history.get.filter(({ url }) =>
        url.includes('/configuration/')
      )
    const before = requests().length
    for (let event = 0; event < 5; event++) {
      await invalidateRunAs()
      await vi.advanceTimersByTimeAsync(10)
    }
    await vi.advanceTimersByTimeAsync(100)
    expect(requests()).toHaveLength(before)
    patch.resolve(200, completeConfiguration({ instructions: 'Changed' }))
    await flushPromises()
    expect(requests()).toHaveLength(before + 1)
    expect(requests().at(-1).headers['X-Baserow-Realtime-Recovery']).toBe(
      'true'
    )
  })

  test('rejects only the unavailable choice and saves other pending edits', async () => {
    testApp.dontFailOnErrorResponses()
    const patch = deferredReply()
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
      200,
      page([
        {
          id: 'core.Agent:7',
          subject_type: 'core.Agent',
          subject_id: 7,
          name: 'Investor',
        },
      ])
    )
    mockSaves(
      testApp,
      patch.reply,
      completeConfiguration({ instructions: 'Keep my draft', run_as: null })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Keep my draft')
    await wrapper.get('button[aria-label="action.back"]').trigger('click')
    await openSection(wrapper, 'agent.workspaceAccess')
    await pickRunAs(wrapper, 'Investor')
    mockConfiguration(
      testApp,
      completeConfiguration({ instructions: 'Keep my draft', run_as: null })
    )
    patch.resolve(400, { error: 'ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST' })
    await flushPromises()
    expect(savedValues(testApp)).toEqual([
      {
        instructions: 'Keep my draft',
        run_as_subject_type: 'core.Agent',
        run_as_subject_id: 7,
      },
      { instructions: 'Keep my draft' },
    ])
    await wrapper.get('button[aria-label="action.back"]').trigger('click')
    await openSection(wrapper, 'agent.instructions')
    expect(instructions(wrapper).element.value).toBe('Keep my draft')
    expect(testApp.store.state.toast.items[0].message).toBe(
      'agent.runAsRejected'
    )
    expect(await leave()).toBe(true)
  })

  test('a late identity rejection preserves and saves a newer choice', async () => {
    testApp.dontFailOnErrorResponses()
    const patch = deferredReply()
    const support = { ...investor, id: 8, name: 'Support', status: 'active' }
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
      200,
      page([
        {
          id: 'core.Agent:7',
          subject_type: 'core.Agent',
          subject_id: 7,
          name: 'Investor',
        },
        {
          id: 'core.Agent:8',
          subject_type: 'core.Agent',
          subject_id: 8,
          name: 'Support',
        },
      ])
    )
    mockSaves(testApp, patch.reply, completeConfiguration({ run_as: support }))
    mockConfiguration(
      testApp,
      completeConfiguration({ run_as: null }),
      completeConfiguration({ run_as: support })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await pickRunAs(wrapper, 'Investor')
    await pickRunAs(wrapper, 'Support')
    patch.resolve(400, { error: 'ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST' })
    await flushPromises()
    expect(savedValues(testApp)).toEqual([
      { run_as_subject_type: 'core.Agent', run_as_subject_id: 7 },
      { run_as_subject_type: 'core.Agent', run_as_subject_id: 8 },
    ])
    expect(wrapper.get('.dropdown__selected-text').text()).toBe('Support')
    expect(testApp.store.state.toast.items).toHaveLength(0)
  })

  test('keeps an identity draft on a network failure so it can be retried', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
      200,
      page([
        {
          id: 'core.Agent:7',
          subject_type: 'core.Agent',
          subject_id: 7,
          name: 'Investor',
        },
      ])
    )
    mockSaves(testApp, [500, {}], completeConfiguration({ run_as: investor }))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await pickRunAs(wrapper, 'Investor')
    expect(wrapper.get('.dropdown__selected-text').text()).toBe('Investor')
    expect(wrapper.get('.agent-configuration__save-status').text()).toContain(
      'action.retry'
    )
    expect(testApp.store.state.toast.items).toHaveLength(0)
    await wrapper
      .get('.agent-configuration__save-status button')
      .trigger('click')
    await flushPromises()
    expect(savedValues(testApp)).toEqual(
      Array(2).fill({ run_as_subject_type: 'core.Agent', run_as_subject_id: 7 })
    )
    expect(wrapper.find('.agent-configuration__save-status').exists()).toBe(
      false
    )
  })

  test('refreshes during a sustained identity event burst instead of postponing indefinitely', async () => {
    useFakeTimers()
    await mount()
    const requests = () =>
      testApp.mock.history.get.filter(({ url }) =>
        url.includes('/configuration/')
      )
    const before = requests().length
    for (let event = 0; event < 8; event++) {
      await invalidateRunAs()
      await vi.advanceTimersByTimeAsync(80)
    }
    expect(requests()).toHaveLength(before + 1)
    await vi.advanceTimersByTimeAsync(100)
    expect(requests()).toHaveLength(before + 2)
  })

  test('keeps rejected-choice recovery failures separate from dirty edits', async () => {
    testApp.dontFailOnErrorResponses()
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
      200,
      page([
        {
          id: 'core.Agent:7',
          subject_type: 'core.Agent',
          subject_id: 7,
          name: 'Investor',
        },
      ])
    )
    mockSaves(testApp, [
      400,
      { error: 'ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST' },
    ])
    mockConfiguration(testApp, completeConfiguration({ run_as: null }), [
      500,
      {},
    ])
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await pickRunAs(wrapper, 'Investor')
    expect(wrapper.get('.dropdown__selected-text').text()).toBe(
      'agent.noWorkspaceAccess'
    )
    expect(wrapper.find('.agent-configuration__save-status').exists()).toBe(
      false
    )
    expect(warning(wrapper).exists()).toBe(true)
    expect(await leave()).toBe(true)
    expect(savedValues(testApp)).toHaveLength(1)
  })

  test('does not fetch private configuration for identity events without access', async () => {
    useFakeTimers()
    allowed.value = withoutConfiguration
    const wrapper = await mount()

    await invalidateRunAs()
    await vi.advanceTimersByTimeAsync(100)
    await flushPromises()

    expect(
      testApp.mock.history.get.filter(({ url }) =>
        url.includes('/configuration/')
      )
    ).toEqual([])
    expect(wrapper.find('.agent-configuration').exists()).toBe(false)
  })

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
      testApp.mock.onGet('/agent/10/run-as-subjects/').reply(200, page([]))
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

  describe('web search', () => {
    const setting = (wrapper) => wrapper.get('.agent-web-search')
    const webSearch = (extra = {}) =>
      completeConfiguration({
        web_search_enabled: false,
        web_search_available: true,
        allowed_tools: [],
        ...extra,
      })

    test('is off by default and saves when turned on', async () => {
      mockConfiguration(testApp, webSearch())
      mockSaves(testApp, webSearch({ web_search_enabled: true }))
      const wrapper = await mount()
      await openSection(wrapper, 'agent.agentSettings')

      const input = setting(wrapper).findComponent({ name: 'SwitchInput' })
      expect(input.props('modelValue')).toBe(false)
      expect(input.props('disabled')).toBe(false)

      input.vm.$emit('update:modelValue', true)
      await flushPromises()

      expect(savedValues(testApp)).toEqual([{ web_search_enabled: true }])
      expect(input.props('modelValue')).toBe(true)
    })

    test('explains that an unsupported model cannot search', async () => {
      mockConfiguration(testApp, webSearch({ web_search_available: false }))
      const wrapper = await mount()
      await openSection(wrapper, 'agent.agentSettings')

      const input = setting(wrapper).findComponent({ name: 'SwitchInput' })
      expect(input.props('disabled')).toBe(true)
      expect(input.props('modelValue')).toBe(false)
      expect(
        setting(wrapper).get('.agent-web-search__unavailable').text()
      ).toBe('agent.webSearchUnavailable')
    })

    test('explains when the model cannot search alongside workspace tools', async () => {
      mockConfiguration(
        testApp,
        webSearch({
          web_search_available: false,
          web_search_blocked_by_tools: true,
          run_as: investor,
          allowed_tools: ['list_tables'],
        })
      )
      const wrapper = await mount()
      await openSection(wrapper, 'agent.agentSettings')

      const input = setting(wrapper).findComponent({ name: 'SwitchInput' })
      expect(input.props('disabled')).toBe(true)
      expect(
        setting(wrapper).get('.agent-web-search__unavailable').text()
      ).toBe('agent.webSearchBlockedByTools')
    })

    test.each([
      { provider_type: null, model_identifier: null },
      { model_identifier: null },
    ])(
      'says nothing about the model before one is chosen: %j',
      async (extra) => {
        mockConfiguration(
          testApp,
          webSearch({
            web_search_available: false,
            web_search_enabled: true,
            ...extra,
          })
        )
        const wrapper = await mount()
        await openSection(wrapper, 'agent.agentSettings')

        expect(
          setting(wrapper).find('.agent-web-search__unavailable').exists()
        ).toBe(false)
        expect(setting(wrapper).findComponent({ name: 'Badge' }).exists()).toBe(
          false
        )
      }
    )

    test('can be turned off after the model stopped supporting it', async () => {
      mockConfiguration(
        testApp,
        webSearch({ web_search_available: false, web_search_enabled: true })
      )
      mockSaves(
        testApp,
        webSearch({ web_search_available: false, web_search_enabled: false })
      )
      const wrapper = await mount()
      await openSection(wrapper, 'agent.agentSettings')

      const input = setting(wrapper).findComponent({ name: 'SwitchInput' })
      expect(input.props('disabled')).toBe(false)
      // The saved choice stays on, but it shows at a glance that it can't run.
      expect(setting(wrapper).findComponent({ name: 'Badge' }).text()).toBe(
        'agent.webSearchUnavailableBadge'
      )
      expect(
        setting(wrapper).get('.agent-web-search__unavailable').classes()
      ).toContain('alert--warning')
      expect(
        setting(wrapper).get('.agent-web-search__unavailable').text()
      ).toBe('agent.webSearchUnavailableWhileOn')

      expect(input.props('modelValue')).toBe(true)
      await setting(wrapper).get('.switch').trigger('click')
      await flushPromises()

      expect(savedValues(testApp)).toEqual([{ web_search_enabled: false }])
      expect(input.props('modelValue')).toBe(false)
      expect(input.props('disabled')).toBe(true)
      expect(setting(wrapper).findComponent({ name: 'Badge' }).exists()).toBe(
        false
      )
    })

    test.each([
      [true, investor, ['list_tables'], true],
      [false, investor, ['list_tables'], false],
      [true, null, [], false],
      [true, investor, [], false],
    ])(
      'warns only when searching can reach workspace data (%s, %j, %j)',
      async (enabled, runAs, allowedTools, warned) => {
        mockConfiguration(
          testApp,
          webSearch({
            web_search_enabled: enabled,
            run_as: runAs,
            allowed_tools: allowedTools,
          })
        )
        const wrapper = await mount()
        await openSection(wrapper, 'agent.agentSettings')

        expect(setting(wrapper).find('.alert').exists()).toBe(warned)
      }
    )
  })

  const withTools = (
    allowedTools,
    { askFirstTools = [], runAs = investor } = {}
  ) =>
    completeConfiguration({
      run_as: runAs,
      allowed_tools: allowedTools,
      ask_first_tools: askFirstTools,
      available_tools: [
        { name: 'list_tables', group: 'database', changes_data: false },
        { name: 'create_rows', group: 'database', changes_data: true },
        { name: 'delete_rows', group: 'database', changes_data: true },
      ],
    })
  const inModal = (selector, text) =>
    [...document.body.querySelectorAll(selector)].find((element) =>
      element.textContent.includes(text)
    )
  const modalInputs = (column) => [
    ...document.body.querySelectorAll(
      `.agent-tool-permissions__${column} input`
    ),
  ]
  const toolInput = (tool, column) =>
    inModal('.agent-tool-permissions__tool', tool).querySelector(
      `.agent-tool-permissions__${column} input`
    )
  const toolsSummary = () =>
    document.body
      .querySelector('.agent-tool-permissions__summary')
      .textContent.trim()
  const clickDone = () =>
    inModal(
      '.agent-tool-permissions__actions button',
      'agent.toolsDone'
    ).click()
  const askSwitch = (wrapper) =>
    wrapper.get('.agent-workspace-tools__ask [role="checkbox"]')
  const groupCount = (wrapper) =>
    wrapper.get('.agent-workspace-tools__group-count').text()

  test.each(['Enter', ' '])(
    'enables workspace tools with %s and opens named tool permissions',
    async (key) => {
      mockConfiguration(testApp, withTools([]))
      mockSaves(
        testApp,
        withTools(['list_tables']),
        withTools(['list_tables', 'create_rows'], {
          askFirstTools: ['create_rows'],
        })
      )
      const wrapper = await mount()
      await openSection(wrapper, 'agent.workspaceAccess')
      const tools = wrapper.get('.agent-workspace-tools')
      const toggle = tools.get('[role="switch"]')
      expect(toggle.attributes('aria-label')).toBe('agent.workspaceTools')
      expect(toggle.attributes('aria-checked')).toBe('false')
      expect(toggle.element.tabIndex).toBe(0)
      toggle.element.focus()
      expect(document.activeElement).toBe(toggle.element)

      await toggle.trigger('keydown', { key })
      await flushPromises()

      expect(toggle.attributes('aria-checked')).toBe('true')
      const group = tools.get('button.agent-workspace-tools__group')
      group.element.focus()
      expect(document.activeElement).toBe(group.element)
      await group.trigger('click')
      await flushPromises()
      const label = (input) => input.labels[0].textContent.trim()
      expect(modalInputs('allow').map(label)).toEqual([
        'agent.toolListTables',
        'agent.toolCreateRows',
        'agent.toolDeleteRows',
      ])
      expect(modalInputs('ask-first').map(label)).toEqual(
        Array(3).fill('agent.toolAskFirstLabel')
      )
      modalInputs('allow')[1].click()
      clickDone()
      await flushPromises()

      expect(savedValues(testApp)).toEqual([
        { allowed_tools: ['list_tables'], ask_first_tools: [] },
        {
          allowed_tools: ['list_tables', 'create_rows'],
          ask_first_tools: ['create_rows'],
        },
      ])
    }
  )

  test('saves a newly allowed change tool without Ask first once unchecked', async () => {
    mockConfiguration(testApp, withTools(['list_tables']))
    mockSaves(testApp, withTools(['list_tables', 'create_rows']))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await wrapper.get('.agent-workspace-tools__group').trigger('click')
    await flushPromises()

    toolInput('agent.toolCreateRows', 'allow').click()
    await flushPromises()
    const askFirst = toolInput('agent.toolCreateRows', 'ask-first')
    expect([askFirst.checked, askFirst.disabled]).toEqual([true, false])
    expect(toolInput('agent.toolDeleteRows', 'ask-first').disabled).toBe(true)
    expect(toolsSummary()).toBe('agent.toolsAskFirstSummary - 1')

    askFirst.click()
    await flushPromises()
    expect(toolsSummary()).toBe('agent.toolsAskFirstSummary - 0')
    clickDone()
    await flushPromises()

    expect(savedValues(testApp)).toEqual([
      { allowed_tools: ['list_tables', 'create_rows'], ask_first_tools: [] },
    ])
  })

  test('keeps a pending tool choice whole when another member changes tools', async () => {
    testApp.dontFailOnErrorResponses()
    mockConfiguration(testApp, withTools(['list_tables']))
    mockSaves(testApp, [500, {}], withTools(['list_tables', 'create_rows']))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await wrapper.get('.agent-workspace-tools__group').trigger('click')
    await flushPromises()
    toolInput('agent.toolCreateRows', 'allow').click()
    await flushPromises()
    toolInput('agent.toolCreateRows', 'ask-first').click()
    clickDone()
    await flushPromises()
    mockConfiguration(
      testApp,
      withTools(['list_tables', 'delete_rows'], {
        askFirstTools: ['delete_rows'],
      })
    )

    await remoteUpdate(testApp, agent)
    await wrapper
      .get('.agent-configuration__save-status button')
      .trigger('click')
    await flushPromises()

    expect(savedValues(testApp).at(-1)).toEqual({
      allowed_tools: ['list_tables', 'create_rows'],
      ask_first_tools: [],
    })
  })

  test('keeps workspace tool controls inactive for a read-only member', async () => {
    allowed.value = (operation) => operation !== 'application.update'
    mockConfiguration(testApp, withTools(['list_tables', 'create_rows']))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    const tools = wrapper.get('.agent-workspace-tools')
    const toggle = tools.get('[role="switch"]')
    expect(toggle.attributes('aria-disabled')).toBe('true')
    expect(toggle.element.tabIndex).toBe(-1)
    expect(
      tools.get('button.agent-workspace-tools__group').element.disabled
    ).toBe(true)
    expect(askSwitch(wrapper).attributes('aria-disabled')).toBe('true')

    await toggle.trigger('keydown', { key: 'Enter' })
    await toggle.trigger('keydown', { key: ' ' })
    await askSwitch(wrapper).trigger('keydown', { key: 'Enter' })
    await tools.get('.segment-control__button').trigger('click')
    await flushPromises()

    expect(toggle.attributes('aria-checked')).toBe('true')
    expect(savedValues(testApp)).toEqual([])
  })

  test('clears workspace tools when no workspace access is selected', async () => {
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(200, page([]))
    mockConfiguration(testApp, withTools(['list_tables', 'create_rows']))
    mockSaves(testApp, withTools([], { runAs: null }))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await pickRunAs(wrapper, 'agent.noWorkspaceAccess')

    const tools = wrapper.get('.agent-workspace-tools')
    const toggle = tools.get('[role="switch"]')
    expect(toggle.attributes('aria-checked')).toBe('false')
    expect(toggle.attributes('aria-disabled')).toBe('true')
    expect(toggle.element.tabIndex).toBe(-1)
    expect(tools.find('.agent-workspace-tools__presets').exists()).toBe(false)
    expect(tools.get('.agent-workspace-tools__description').text()).toBe(
      'agent.toolsRequireIdentity'
    )
    expect(wrapper.find('.alert--warning').exists()).toBe(false)
    expect(savedValues(testApp)).toEqual([
      {
        run_as_subject_type: null,
        run_as_subject_id: null,
        allowed_tools: [],
        ask_first_tools: [],
      },
    ])
    await wrapper.get('button[aria-label="action.back"]').trigger('click')
    expect(workspaceAccessRow(wrapper).find('.icon--error').exists()).toBe(
      false
    )
  })

  test('requires an identity before tools can be enabled and keeps them off after selection', async () => {
    mockConfiguration(testApp, withTools([], { runAs: null }))
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
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
    mockSaves(testApp, withTools([]))
    const wrapper = await mount()
    expect(workspaceAccessRow(wrapper).find('.icon--error').exists()).toBe(
      false
    )
    await openSection(wrapper, 'agent.workspaceAccess')
    const tools = wrapper.get('.agent-workspace-tools')
    const toggle = tools.get('[role="switch"]')
    expect(toggle.attributes('aria-checked')).toBe('false')
    expect(toggle.attributes('aria-disabled')).toBe('true')
    expect(tools.get('.agent-workspace-tools__description').text()).toBe(
      'agent.toolsRequireIdentity'
    )

    await toggle.trigger('click')
    await toggle.trigger('keydown', { key: 'Enter' })
    await toggle.trigger('keydown', { key: ' ' })
    await flushPromises()
    expect(savedValues(testApp)).toEqual([])
    expect(toggle.attributes('aria-checked')).toBe('false')

    await pickRunAs(wrapper, 'Investor')
    expect(toggle.attributes('aria-checked')).toBe('false')
    expect(toggle.attributes('aria-disabled')).toBe('false')
    expect(tools.get('.agent-workspace-tools__description').text()).toBe(
      'agent.workspaceToolsDescription'
    )
    expect(savedValues(testApp)).toEqual([
      { run_as_subject_type: 'core.Agent', run_as_subject_id: 7 },
    ])
  })

  test('keeps explicit tool activation while the identity selection is still saving', async () => {
    const patch = deferredReply()
    mockConfiguration(testApp, withTools([], { runAs: null }))
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
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
    mockSaves(testApp, patch.reply, withTools(['list_tables']))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')

    await pickRunAs(wrapper, 'Investor')
    const toggle = wrapper.get('.agent-workspace-tools [role="switch"]')
    expect(toggle.attributes('aria-disabled')).toBe('false')
    expect(toggle.attributes('aria-checked')).toBe('false')
    await toggle.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(toggle.attributes('aria-checked')).toBe('true')
    expect(savedValues(testApp)).toEqual([
      { run_as_subject_type: 'core.Agent', run_as_subject_id: 7 },
    ])

    patch.resolve(200, withTools([]))
    await flushPromises()

    expect(toggle.attributes('aria-checked')).toBe('true')
    expect(savedValues(testApp)).toEqual([
      { run_as_subject_type: 'core.Agent', run_as_subject_id: 7 },
      { allowed_tools: ['list_tables'], ask_first_tools: [] },
    ])
  })

  test('does not reactivate legacy tool settings when selecting an identity from no workspace access', async () => {
    mockConfiguration(
      testApp,
      withTools(['list_tables', 'create_rows'], { runAs: null })
    )
    testApp.mock.onGet('/agent/10/run-as-subjects/').reply(
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
    mockSaves(testApp, withTools([]))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    const tools = wrapper.get('.agent-workspace-tools')
    expect(tools.get('[role="switch"]').attributes('aria-checked')).toBe(
      'false'
    )
    expect(tools.find('.agent-workspace-tools__presets').exists()).toBe(false)

    await pickRunAs(wrapper, 'Investor')

    expect(tools.get('[role="switch"]').attributes('aria-checked')).toBe(
      'false'
    )
    expect(savedValues(testApp)).toEqual([
      {
        run_as_subject_type: 'core.Agent',
        run_as_subject_id: 7,
        allowed_tools: [],
        ask_first_tools: [],
      },
    ])
  })

  test.each([
    [
      'trashed',
      { ...investor, trashed: true, status: 'trashed' },
      'agent.runAsTrashed',
    ],
    [
      'missing',
      { ...investor, name: null, status: 'missing' },
      'agent.runAsMissing',
    ],
  ])(
    'keeps saved tools visible but inactive with a selected %s identity',
    async (_, identity, errorMessage) => {
      mockConfiguration(
        testApp,
        withTools(['list_tables', 'create_rows'], { runAs: identity })
      )
      const wrapper = await mount()
      expect(
        workspaceAccessRow(wrapper).get('.icon--error').attributes('aria-label')
      ).toBe(errorMessage)
      await openSection(wrapper, 'agent.workspaceAccess')
      const body = wrapper.get('.agent-configuration__body')
      const tools = body.get('.agent-workspace-tools')
      expect(body.get('.control__messages--error').text()).toBe(errorMessage)
      expect(body.find('.alert--warning').exists()).toBe(false)
      const toggle = tools.get('[role="switch"]')
      expect(toggle.attributes('aria-checked')).toBe('true')
      expect(toggle.attributes('aria-disabled')).toBe('true')
      expect(tools.get('.agent-workspace-tools__group').element.disabled).toBe(
        true
      )
      expect(tools.get('.agent-workspace-tools__group').text()).toContain(
        'agent.toolsSelected'
      )
      expect(
        tools
          .findAll('.segment-control__button')
          .every((button) => button.element.disabled)
      ).toBe(true)
      expect(tools.get('.agent-workspace-tools__description').text()).toBe(
        'agent.toolsRequireIdentity'
      )

      await toggle.trigger('keydown', { key: 'Enter' })
      await tools.get('.segment-control__button').trigger('click')
      await tools.get('.agent-workspace-tools__group').trigger('click')
      await flushPromises()

      expect(savedValues(testApp)).toEqual([])
      expect(
        document.body.querySelector('.agent-tool-permissions__tool')
      ).toBeNull()
    }
  )

  test('restores saved tools and clears the section error when the identity becomes available again', async () => {
    mockConfiguration(
      testApp,
      withTools(['create_rows'], { runAs: { ...investor, trashed: true } })
    )
    const wrapper = await mount()
    expect(workspaceAccessRow(wrapper).find('.icon--error').exists()).toBe(true)
    await openSection(wrapper, 'agent.workspaceAccess')
    const body = wrapper.get('.agent-configuration__body')
    const toggle = body.get('.agent-workspace-tools [role="switch"]')
    expect(toggle.attributes('aria-checked')).toBe('true')
    expect(toggle.attributes('aria-disabled')).toBe('true')

    mockConfiguration(testApp, withTools(['create_rows']))
    await remoteUpdate(testApp, agent)

    expect(body.find('.control__messages--error').exists()).toBe(false)
    expect(body.find('.alert--warning').exists()).toBe(false)
    expect(toggle.attributes('aria-checked')).toBe('true')
    expect(toggle.attributes('aria-disabled')).toBe('false')
    await wrapper.get('button[aria-label="action.back"]').trigger('click')
    expect(workspaceAccessRow(wrapper).find('.icon--error').exists()).toBe(
      false
    )
    expect(savedValues(testApp)).toEqual([])
  })

  test('disables an open tool permissions modal when edit access is revoked', async () => {
    mockConfiguration(
      testApp,
      withTools(['list_tables', 'create_rows'], {
        askFirstTools: ['create_rows'],
      })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await wrapper.get('.agent-workspace-tools__group').trigger('click')
    await flushPromises()

    allowed.value = (operation) => operation !== 'application.update'
    await flushPromises()

    const inputs = [...modalInputs('allow'), ...modalInputs('ask-first')]
    expect(inputs).toHaveLength(6)
    expect(inputs.every((input) => input.disabled)).toBe(true)
    const done = inModal(
      '.agent-tool-permissions__actions button',
      'agent.toolsDone'
    )
    expect(done.disabled).toBe(true)
    done.click()
    expect(savedValues(testApp)).toEqual([])
  })

  test('allows workspace tools with presets or one by one', async () => {
    const everything = ['list_tables', 'create_rows', 'delete_rows']
    mockConfiguration(testApp, withTools(['list_tables', 'create_rows']))
    mockSaves(
      testApp,
      withTools(everything, { askFirstTools: ['delete_rows'] }),
      withTools(['list_tables', 'create_rows']),
      withTools([])
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    await flushPromises()
    const tools = () => wrapper.get('.agent-workspace-tools')
    expect(tools().get('.segment-control__button--active').text()).toBe(
      'agent.toolsCustom'
    )

    await tools()
      .findAll('.segment-control__button')
      .find((button) => button.text() === 'agent.toolsEverything')
      .trigger('click')
    await flushPromises()
    await tools().get('.agent-workspace-tools__group').trigger('click')
    await flushPromises()
    toolInput('agent.toolDeleteRows', 'allow').click()
    clickDone()
    await flushPromises()
    await tools().get('.switch').trigger('click')
    await flushPromises()

    expect(savedValues(testApp)).toEqual([
      { allowed_tools: everything, ask_first_tools: ['delete_rows'] },
      { allowed_tools: ['list_tables', 'create_rows'], ask_first_tools: [] },
      { allowed_tools: [], ask_first_tools: [] },
    ])
    expect(wrapper.find('.agent-workspace-tools__group').exists()).toBe(false)
  })

  test('shows an unknown reasoning effort as the model default', async () => {
    mockConfiguration(
      testApp,
      completeConfiguration({ reasoning_effort: 'xhigh' })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')

    expect(
      reasoningEffortDropdown(wrapper).get('.dropdown__selected-text').text()
    ).toBe('agent.reasoningEffortDefault')
  })

  test('saves the reasoning effort and saves the model default as null', async () => {
    mockSaves(
      testApp,
      completeConfiguration({ reasoning_effort: 'high' }),
      completeConfiguration({ reasoning_effort: null })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    const dropdown = () => reasoningEffortDropdown(wrapper)
    expect(dropdown().get('.dropdown__selected-text').text()).toBe(
      'agent.reasoningEffortDefault'
    )

    await choose(dropdown(), 'agent.reasoningEffortHigh')
    await flushPromises()
    expect(dropdown().get('.dropdown__selected-text').text()).toBe(
      'agent.reasoningEffortHigh'
    )
    await choose(dropdown(), 'agent.reasoningEffortDefault')
    await flushPromises()

    expect(savedValues(testApp)).toEqual([
      { reasoning_effort: 'high' },
      { reasoning_effort: null },
    ])
  })

  test.each([
    ['low', 'high', 'agent.reasoningEffortAdjusted'],
    ['high', null, 'agent.reasoningEffortNotSupported'],
    ['high', 'high', null],
  ])(
    'explains when the model replies with another effort than %s',
    async (effort, applied, note) => {
      mockConfiguration(
        testApp,
        completeConfiguration({
          reasoning_effort: effort,
          applied_reasoning_effort: applied,
        })
      )
      const wrapper = await mount()
      await openSection(wrapper, 'agent.agentSettings')

      const warning = reasoningEffortWarning(wrapper)
      if (note) expect(warning.text()).toBe(note)
      else expect(warning.exists()).toBe(false)
    }
  )

  test('explains the effort the saved choice replies with', async () => {
    mockSaves(
      testApp,
      completeConfiguration({
        reasoning_effort: 'off',
        applied_reasoning_effort: 'low',
      })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    const warning = () => reasoningEffortWarning(wrapper)

    await choose(reasoningEffortDropdown(wrapper), 'agent.reasoningEffortOff')
    expect(warning().exists()).toBe(false)
    await flushPromises()

    expect(warning().text()).toBe('agent.reasoningEffortAdjusted')
  })

  test('asks before every allowed change or none, keeping read tools as they are', async () => {
    const everything = ['list_tables', 'create_rows', 'delete_rows']
    mockConfiguration(
      testApp,
      withTools(everything, { askFirstTools: ['list_tables', 'create_rows'] })
    )
    mockSaves(
      testApp,
      withTools(everything, { askFirstTools: everything }),
      withTools(everything, { askFirstTools: ['list_tables'] })
    )
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    expect(askSwitch(wrapper).attributes('aria-checked')).toBe('mixed')
    expect(askSwitch(wrapper).classes()).toContain('switch--indeterminate')
    expect(groupCount(wrapper)).toBe(
      'agent.toolsSummary • agent.toolsAskCount - 2'
    )

    await askSwitch(wrapper).trigger('click')
    await flushPromises()
    expect(askSwitch(wrapper).attributes('aria-checked')).toBe('true')
    await askSwitch(wrapper).trigger('keydown', { key: ' ' })
    await flushPromises()

    expect(askSwitch(wrapper).attributes('aria-checked')).toBe('false')
    expect(groupCount(wrapper)).toBe(
      'agent.toolsSummary • agent.toolsAskCount - 1'
    )
    expect(savedValues(testApp)).toEqual([
      { allowed_tools: everything, ask_first_tools: everything },
      { allowed_tools: everything, ask_first_tools: ['list_tables'] },
    ])
  })

  test('locks the ask switch while no change tool is allowed', async () => {
    mockConfiguration(testApp, withTools(['list_tables']))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.workspaceAccess')
    const ask = askSwitch(wrapper)
    expect(ask.attributes('aria-checked')).toBe('false')
    expect(ask.attributes('aria-disabled')).toBe('true')
    expect(ask.element.tabIndex).toBe(-1)

    await ask.trigger('click')
    await ask.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(groupCount(wrapper)).toBe('agent.toolsSummary')
    expect(savedValues(testApp)).toEqual([])
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

    expect(wrapper.findAll('.menu-list__item-button')).toHaveLength(4)
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
