import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { matchedRouteKey } from 'vue-router'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import {
  agentData,
  choose,
  completeConfiguration,
  debounce,
  deferredReply,
  dropdowns,
  editInstructions,
  fieldError,
  incompleteConfiguration,
  instructions,
  mountAgentContent,
  openSection,
  saving,
  useFakeTimers,
  warning,
  withoutSettings,
  workspace,
} from './helpers'

describe('Agent configuration', () => {
  let testApp
  let agent
  let allowed

  beforeEach(async () => {
    testApp = new TestApp()
    allowed = ref(() => true)
    await testApp.store.dispatch('workspace/forceCreate', clone(workspace))
    agent = await testApp.store.dispatch('application/forceCreate', agentData)
    testApp.mock.onGet('/workspaces/').reply(200, [workspace])
    testApp.mock.onGet('/agent/10/readiness/').reply(200, { state: 'ready' })
    testApp.mock
      .onGet('/agent/10/configuration/')
      .reply(200, completeConfiguration())
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  const mountContent = (provide) =>
    mountAgentContent(testApp, agent, allowed, provide)

  test('autosaves after a pause and shows only the header spinner while saving', async () => {
    useFakeTimers()
    const patch = deferredReply()
    testApp.mock.onPatch('/agent/10/configuration/').reply(patch.reply)
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Updated instructions')
    expect(testApp.mock.history.patch).toHaveLength(0)
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
    testApp.mock.onPatch('/agent/10/configuration/').replyOnce(first.reply)
    testApp.mock
      .onPatch('/agent/10/configuration/')
      .reply(200, completeConfiguration())
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Changed instructions')
    await instructions(wrapper).setValue('Be helpful.')
    await debounce()
    expect(testApp.mock.history.patch).toHaveLength(1)

    first.resolve(
      200,
      completeConfiguration({ instructions: 'Changed instructions' })
    )
    await flushPromises()
    expect(instructions(wrapper).element.value).toBe('Be helpful.')
    await debounce()

    expect(JSON.parse(testApp.mock.history.patch[1].data)).toEqual({
      instructions: 'Be helpful.',
    })
    expect(instructions(wrapper).element.value).toBe('Be helpful.')
  })

  test('saves pending edits before leaving the Agent', async () => {
    const record = { leaveGuards: new Set(), updateGuards: new Set() }
    const first = deferredReply()
    const second = deferredReply()
    testApp.mock.onPatch('/agent/10/configuration/').replyOnce(first.reply)
    testApp.mock.onPatch('/agent/10/configuration/').replyOnce(second.reply)
    const wrapper = await mountContent({ [matchedRouteKey]: ref(record) })
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Changed instructions')
    await instructions(wrapper).setValue('Be helpful.')
    const completed = vi.fn()
    const leaving = [...record.leaveGuards][0]().then((result) => {
      completed(result)
      return result
    })

    first.resolve(
      200,
      completeConfiguration({ instructions: 'Changed instructions' })
    )
    await flushPromises()
    expect(completed).not.toHaveBeenCalled()
    second.resolve(200, completeConfiguration())

    expect(await leaving).toBe(true)
    expect(testApp.mock.history.patch).toHaveLength(2)
  })

  test('stays on the Agent with the draft when saving before leaving fails', async () => {
    testApp.dontFailOnErrorResponses()
    const record = { leaveGuards: new Set(), updateGuards: new Set() }
    testApp.mock.onPatch('/agent/10/configuration/').reply(500, {})
    const wrapper = await mountContent({ [matchedRouteKey]: ref(record) })
    await openSection(wrapper, 'agent.instructions')
    await instructions(wrapper).setValue('Unsaved instructions')

    expect(await [...record.leaveGuards][0]()).toBe(false)
    await flushPromises()

    expect(instructions(wrapper).element.value).toBe('Unsaved instructions')
    expect(wrapper.text()).toContain('agent.configurationSaveError')
  })

  test('keeps a failed model save without a required error until retry succeeds', async () => {
    useFakeTimers()
    testApp.dontFailOnErrorResponses()
    testApp.mock
      .onGet('/agent/10/configuration/')
      .reply(200, incompleteConfiguration('model_identifier'))
    testApp.mock.onPatch('/agent/10/configuration/').replyOnce(500, {})
    testApp.mock
      .onPatch('/agent/10/configuration/')
      .reply(200, completeConfiguration())
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.agentSettings')
    await choose(dropdowns(wrapper)[1], 'model-one')
    await debounce()

    expect(dropdowns(wrapper)[1].classes()).not.toContain('dropdown--error')
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

  test.each([
    ['name', 0],
    ['model_identifier', 2],
  ])(
    'clears the required %s error as soon as it is edited',
    async (field, index) => {
      useFakeTimers()
      testApp.mock
        .onGet('/agent/10/configuration/')
        .reply(200, incompleteConfiguration(field))
      const patch = deferredReply()
      testApp.mock.onPatch('/agent/10/configuration/').reply(patch.reply)
      const wrapper = await mountContent()
      await openSection(wrapper, 'agent.agentSettings')
      expect(fieldError(wrapper, index).text()).toBe('error.requiredField')

      if (field === 'name') {
        await wrapper.get('.agent-configuration input').setValue('Fixed')
      } else {
        await choose(dropdowns(wrapper)[1], 'model-one')
      }

      expect(fieldError(wrapper, index).exists()).toBe(false)
      await debounce()
      expect(fieldError(wrapper, index).exists()).toBe(false)
      patch.resolve(200, completeConfiguration())
      await flushPromises()
      expect(warning(wrapper).exists()).toBe(false)
    }
  )

  test('clears the model when the provider changes and then requires a model', async () => {
    const workspaceWithTwoProviders = {
      ...workspace,
      ai_features: {
        ai_agent: { models: { openai: ['model-one'], anthropic: ['claude'] } },
      },
    }
    testApp.mock.onGet('/workspaces/').reply(200, [workspaceWithTwoProviders])
    testApp.mock.onPatch('/agent/10/configuration/').reply(
      200,
      completeConfiguration({
        provider_type: 'anthropic',
        model_identifier: null,
        state: 'incomplete',
        errors: { model_identifier: 'required' },
      })
    )
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.agentSettings')

    await choose(dropdowns(wrapper)[0], 'anthropic')
    await wrapper.get('.agent-configuration input').trigger('blur')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      provider_type: 'anthropic',
      model_identifier: null,
    })
    expect(fieldError(wrapper, 2).text()).toBe('error.requiredField')
  })

  test('ties an unavailable model error to the selection it was returned for', async () => {
    useFakeTimers()
    testApp.mock.onGet('/agent/10/configuration/').reply(
      200,
      completeConfiguration({
        model_identifier: 'retired-model',
        state: 'unavailable',
        errors: { model_identifier: 'unavailable' },
      })
    )
    const patch = deferredReply()
    testApp.mock.onPatch('/agent/10/configuration/').reply(patch.reply)
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.agentSettings')
    const model = dropdowns(wrapper)[1]
    expect(model.get('.dropdown__selected-text').text()).toBe('retired-model')
    expect(fieldError(wrapper, 2).text()).toBe('agent.modelUnavailable')

    await choose(model, 'model-two')
    expect(fieldError(wrapper, 2).exists()).toBe(false)
    await debounce()
    patch.resolve(
      200,
      completeConfiguration({
        model_identifier: 'model-two',
        state: 'unavailable',
        errors: { model_identifier: 'unavailable' },
      })
    )
    await flushPromises()

    expect(fieldError(wrapper, 2).text()).toBe('agent.modelUnavailable')
  })

  test('does not restore an older required error over a newer queued selection', async () => {
    useFakeTimers()
    const incomplete = incompleteConfiguration('model_identifier')
    testApp.mock.onGet('/agent/10/configuration/').reply(200, incomplete)
    const first = deferredReply()
    testApp.mock.onPatch('/agent/10/configuration/').replyOnce(first.reply)
    testApp.mock
      .onPatch('/agent/10/configuration/')
      .reply(200, completeConfiguration({ model_identifier: 'model-two' }))
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'Updated instructions')
    await wrapper
      .get('.agent-configuration__header button[aria-label="action.back"]')
      .trigger('click')
    await openSection(wrapper, 'agent.agentSettings')
    const model = dropdowns(wrapper)[1]
    await choose(model, 'model-two')

    first.resolve(200, { ...incomplete, instructions: 'Updated instructions' })
    await flushPromises()
    expect(model.get('.dropdown__selected-text').text()).toBe('model-two')
    expect(model.classes()).not.toContain('dropdown--error')
    await debounce()

    expect(JSON.parse(testApp.mock.history.patch[1].data)).toEqual({
      model_identifier: 'model-two',
    })
    expect(model.classes()).not.toContain('dropdown--error')
  })

  test.each([
    ['instructions', 'agent.instructions', '.agent-configuration textarea'],
    ['model_identifier', 'agent.model', '.agent-configuration .dropdown'],
  ])(
    'opens the configuration on the invalid %s field from its warning',
    async (field, label, selector) => {
      testApp.mock
        .onGet('/agent/10/configuration/')
        .reply(200, incompleteConfiguration(field))
      const wrapper = await mountContent()
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
    testApp.mock
      .onPatch('/agent/10/configuration/')
      .reply(200, completeConfiguration({ name: 'Support' }))
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.agentSettings')
    const name = wrapper.get('.agent-configuration input')

    await name.setValue('  Support  ')
    await name.trigger('blur')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1000)

    expect(testApp.mock.history.patch).toHaveLength(1)
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
      testApp.mock
        .onGet('/agent/10/readiness/')
        .reply(200, { state: 'incomplete' })
      testApp.mock
        .onGet('/agent/10/configuration/')
        .reply(200, incompleteConfiguration('instructions'))
      const wrapper = await mountContent()

      expect(wrapper.text()).toContain('agent.configurationPermissionRequired')
      expect(wrapper.find('.agent-chat__warning-link').exists()).toBe(false)
    }
  )

  test('never shows the settings after read access is revoked during a save', async () => {
    const patch = deferredReply()
    testApp.mock.onPatch('/agent/10/configuration/').reply(patch.reply)
    const wrapper = await mountContent()
    await openSection(wrapper, 'agent.instructions')
    await editInstructions(wrapper, 'PRIVATE')

    allowed.value = withoutSettings
    await flushPromises()
    testApp.mock
      .onGet('/agent/10/readiness/')
      .reply(200, { state: 'incomplete' })
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
    const wrapper = await mountContent()
    testApp.mock
      .onGet('/agent/10/readiness/')
      .reply(200, { state: 'unavailable' })

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
    testApp.mock.onGet('/workspaces/').reply(500, {})
    const wrapper = await mountContent()
    expect(wrapper.text()).toContain('agent.readinessLoadError')

    testApp.mock.onGet('/workspaces/').reply(200, [workspace])
    await wrapper.get('.agent-chat__warning button').trigger('click')
    await flushPromises()

    expect(warning(wrapper).exists()).toBe(false)
  })

  test('ignores an availability failure that arrives after a newer refresh', async () => {
    testApp.dontFailOnErrorResponses()
    const wrapper = await mountContent()
    const older = deferredReply()
    const newer = deferredReply()
    const requests = [older, newer]
    testApp.mock.onGet('/workspaces/').reply(() => requests.shift().reply())
    for (let index = 0; index < 2; index++) {
      await testApp.store.dispatch('application/forceUpdate', {
        application: agent,
        data: { name: agent.name },
      })
      await flushPromises()
    }

    newer.resolve(200, [workspace])
    await flushPromises()
    older.resolve(500, {})
    await flushPromises()

    expect(warning(wrapper).exists()).toBe(false)
  })
})
