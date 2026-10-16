import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import {
  choose,
  completeConfiguration,
  createAgentPage,
  debounce,
  deferredReply,
  destroyAgentPage,
  dropdowns,
  editInstructions,
  fieldError,
  incompleteConfiguration,
  instructions,
  mockAvailability,
  mockConfiguration,
  mockReadiness,
  mockSaves,
  mountWithLeaveGuard,
  openSection,
  refreshAvailabilityTwice,
  savedValues,
  saving,
  unavailableModel,
  useFakeTimers,
  warning,
  withoutSettings,
  workspace,
} from './helpers'

describe('Agent configuration', () => {
  let testApp, agent, allowed, mount

  beforeEach(async () => {
    ;({ testApp, agent, allowed, mount } = await createAgentPage())
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

  test('autosaves after a pause and shows only the header spinner while saving', async () => {
    useFakeTimers()
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Updated instructions')
    expect(savedValues(testApp)).toEqual([])
    expect(saving(wrapper).exists()).toBe(false)

    await debounce()
    expect(saving(wrapper).attributes('aria-label')).toBe('agent.saving')
    patch.resolve(
      200,
      completeConfiguration({ instructions: 'Updated instructions' })
    )
    await flushPromises()

    expect(saving(wrapper).exists()).toBe(false)
    expect(warning(wrapper).exists()).toBe(false)
  })

  test('queues an edit made during a save, even back to the saved value', async () => {
    useFakeTimers()
    const first = deferredReply()
    mockSaves(testApp, first.reply, completeConfiguration())
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Changed instructions')
    await instructions(wrapper).setValue('Be helpful.')
    await debounce()

    first.resolve(
      200,
      completeConfiguration({ instructions: 'Changed instructions' })
    )
    await flushPromises()
    await debounce()

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
    const { wrapper, leave } = await mountWithLeaveGuard(mount)
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
    const { wrapper, leave } = await mountWithLeaveGuard(mount)
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Unsaved instructions')

    expect(await leave()).toBe(false)
    await flushPromises()

    expect(instructions(wrapper).element.value).toBe('Unsaved instructions')
    expect(wrapper.text()).toContain('agent.configurationSaveError')
  })

  test('keeps a failed model save without a required error until retry succeeds', async () => {
    useFakeTimers()
    testApp.dontFailOnErrorResponses()
    mockConfiguration(testApp, incompleteConfiguration('model_identifier'))
    mockSaves(testApp, [500, {}], completeConfiguration())
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    await choose(dropdowns(wrapper)[1], 'model-one')
    await debounce()

    expect(fieldError(wrapper, 2).exists()).toBe(false)
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

  test('clears a required error as soon as the field is edited', async () => {
    useFakeTimers()
    mockConfiguration(testApp, incompleteConfiguration('model_identifier'))
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    expect(fieldError(wrapper, 2).text()).toBe('error.requiredField')

    await choose(dropdowns(wrapper)[1], 'model-one')
    expect(fieldError(wrapper, 2).exists()).toBe(false)
    await debounce()
    expect(fieldError(wrapper, 2).exists()).toBe(false)
    patch.resolve(200, completeConfiguration())
    await flushPromises()

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

    await choose(dropdowns(wrapper)[0], 'anthropic')
    await wrapper.get('.agent-configuration input').trigger('blur')
    await flushPromises()

    expect(savedValues(testApp)).toEqual([
      { provider_type: 'anthropic', model_identifier: null },
    ])
    expect(fieldError(wrapper, 2).text()).toBe('error.requiredField')
  })

  test('ties an unavailable model error to the selection it was returned for', async () => {
    useFakeTimers()
    mockConfiguration(testApp, unavailableModel('retired-model'))
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    const model = dropdowns(wrapper)[1]
    expect(model.get('.dropdown__selected-text').text()).toBe('retired-model')
    expect(fieldError(wrapper, 2).text()).toBe('agent.modelUnavailable')

    await choose(model, 'model-two')
    expect(fieldError(wrapper, 2).exists()).toBe(false)
    await debounce()
    patch.resolve(200, unavailableModel('model-two'))
    await flushPromises()

    expect(fieldError(wrapper, 2).text()).toBe('agent.modelUnavailable')
  })

  test('does not restore an older required error over a newer queued selection', async () => {
    useFakeTimers()
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
    await choose(dropdowns(wrapper)[1], 'model-two')

    first.resolve(200, { ...incomplete, instructions: 'Updated instructions' })
    await flushPromises()
    expect(fieldError(wrapper, 2).exists()).toBe(false)
    await debounce()

    expect(savedValues(testApp)[1]).toEqual({ model_identifier: 'model-two' })
    expect(fieldError(wrapper, 2).exists()).toBe(false)
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

  test('accepts the canonical saved name without saving again', async () => {
    useFakeTimers()
    mockSaves(testApp, completeConfiguration({ name: 'Support' }))
    const wrapper = await mount()
    await openSection(wrapper, 'agent.agentSettings')
    const name = wrapper.get('.agent-configuration input')

    await name.setValue('  Support  ')
    await name.trigger('blur')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1000)

    expect(savedValues(testApp)).toHaveLength(1)
    expect(name.element.value).toBe('Support')
    expect(wrapper.get('.agent-application__header-name').text()).toBe(
      'Support'
    )
  })

  test.each([
    ['cannot read', withoutSettings],
    [
      'can read but not edit',
      (operation) => operation !== 'application.update',
    ],
  ])(
    'asks members who %s the settings to contact an administrator',
    async (_, permission) => {
      allowed.value = permission
      mockReadiness(testApp, { state: 'incomplete' })
      mockConfiguration(testApp, incompleteConfiguration('instructions'))
      const wrapper = await mount()

      expect(wrapper.text()).toContain('agent.configurationPermissionRequired')
      expect(wrapper.find('.agent-chat__warning-link').exists()).toBe(false)
    }
  )

  test('never shows the settings after read access is revoked during a save', async () => {
    const patch = deferredReply()
    mockSaves(testApp, patch.reply)
    const wrapper = await mount()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'PRIVATE')

    allowed.value = withoutSettings
    await flushPromises()
    mockReadiness(testApp, { state: 'incomplete' })
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
    allowed.value = withoutSettings
    const wrapper = await mount()
    mockReadiness(testApp, { state: 'unavailable' })

    await testApp.store.dispatch('workspace/forceUpdateGenerativeAIModels', {
      workspaceId: 1,
      generativeAIModelsEnabled: {},
      aiFeatures: { ai_agent: { models: {} } },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('agent.configurationPermissionRequired')
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

  test('ignores an availability failure that arrives after a newer refresh', async () => {
    testApp.dontFailOnErrorResponses()
    const wrapper = await mount()
    const older = deferredReply()
    const newer = deferredReply()
    mockAvailability(testApp, older.reply, newer.reply)
    await refreshAvailabilityTwice(testApp, agent)

    newer.resolve(200, [workspace])
    await flushPromises()
    older.resolve(500, {})
    await flushPromises()

    expect(warning(wrapper).exists()).toBe(false)
  })
})
