import { vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { matchedRouteKey } from 'vue-router'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import AgentApplicationContent from '@baserow/modules/agent/components/AgentApplicationContent'

export const workspace = {
  id: 1,
  name: 'Workspace',
  generative_ai_models_enabled: { openai: ['model-one', 'model-two'] },
  ai_features: { ai_agent: { models: { openai: ['model-one', 'model-two'] } } },
}

export const agentData = {
  id: 10,
  name: 'Support agent',
  type: 'agent',
  workspace: { id: 1 },
}

export const completeConfiguration = (extra = {}) => ({
  name: 'Support agent',
  instructions: 'Be helpful.',
  provider_type: 'openai',
  model_identifier: 'model-one',
  state: 'ready',
  errors: {},
  ...extra,
})

export const incompleteConfiguration = (field) =>
  completeConfiguration({
    [field]: ['name', 'instructions'].includes(field) ? '' : null,
    state: 'incomplete',
    errors: { [field]: 'required' },
  })

export const unavailableModel = (model) =>
  completeConfiguration({
    model_identifier: model,
    state: 'unavailable',
    errors: { model_identifier: 'unavailable' },
  })

export const deferredReply = () => {
  let resolve
  return {
    reply: () =>
      new Promise((r) => {
        resolve = r
      }),
    resolve: (status, data) => resolve([status, data]),
  }
}

export const withoutSettings = (operation) =>
  !['agent_application.read_settings', 'application.update'].includes(operation)

// One handler per route, because axios-mock-adapter matches an earlier reply first.
export function respond(handler, ...responses) {
  const queue = [...responses]
  handler.reply((config) => {
    const response = queue.length > 1 ? queue.shift() : queue[0]
    if (typeof response === 'function') return response(config)
    const isTuple = Array.isArray(response) && typeof response[0] === 'number'
    return isTuple ? response : [200, response]
  })
}

export const mockReadiness = (testApp, ...responses) =>
  respond(testApp.mock.onGet('/agent/10/readiness/'), ...responses)

export const mockConfiguration = (testApp, ...responses) =>
  respond(testApp.mock.onGet('/agent/10/configuration/'), ...responses)

export const mockSaves = (testApp, ...responses) =>
  respond(testApp.mock.onPatch('/agent/10/configuration/'), ...responses)

export const mockAvailability = (testApp, ...responses) =>
  respond(testApp.mock.onGet('/workspaces/'), ...responses)

export const savedValues = (testApp) =>
  testApp.mock.history.patch.map(({ data }) => JSON.parse(data))

export function mountAgentContent(testApp, agent, allowed, provide = {}) {
  // Nuxt's $hasPermission is a non-configurable getter, so override a child.
  const permissionApp = Object.create(testApp.nuxtApp)
  Object.defineProperty(permissionApp, '$hasPermission', {
    value: (operation) => allowed.value(operation),
  })
  return testApp.mount(AgentApplicationContent, {
    props: { agent },
    global: {
      provide,
      plugins: [{ install: (app) => (app.$nuxt = permissionApp) }],
    },
  })
}

export async function createAgentPage() {
  const testApp = new TestApp()
  const allowed = ref(() => true)
  await testApp.store.dispatch('workspace/forceCreate', clone(workspace))
  const agent = await testApp.store.dispatch(
    'application/forceCreate',
    agentData
  )
  mockAvailability(testApp, [workspace])
  mockReadiness(testApp, { state: 'ready' })
  mockConfiguration(testApp, completeConfiguration())
  return {
    testApp,
    agent,
    allowed,
    mount: (provide) => mountAgentContent(testApp, agent, allowed, provide),
  }
}

export async function destroyAgentPage(testApp) {
  await testApp.afterEach()
  vi.restoreAllMocks()
  vi.clearAllTimers()
  vi.useRealTimers()
}

export async function mountWithLeaveGuard(mount) {
  const record = { leaveGuards: new Set(), updateGuards: new Set() }
  const wrapper = await mount({ [matchedRouteKey]: ref(record) })
  return { wrapper, leave: () => [...record.leaveGuards][0]() }
}

export const useFakeTimers = () =>
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })

export async function debounce() {
  await vi.advanceTimersByTimeAsync(400)
  await flushPromises()
}

export async function refreshAvailabilityTwice(testApp, agent) {
  for (let index = 0; index < 2; index++) {
    await testApp.store.dispatch('application/forceUpdate', {
      application: agent,
      data: { name: agent.name },
    })
    await flushPromises()
  }
}

export const warning = (wrapper) => wrapper.find('.agent-chat__warning')

export const saving = (wrapper) =>
  wrapper.find('.agent-configuration__header [role="status"]')

export const openSection = (wrapper, key) =>
  wrapper
    .findAll('.agent-configuration__section')
    .find((button) => button.text().includes(key))
    .trigger('click')

export const instructions = (wrapper) =>
  wrapper.get('.agent-configuration textarea')

export async function editInstructions(wrapper, value) {
  await instructions(wrapper).setValue(value)
  await instructions(wrapper).trigger('blur')
  await flushPromises()
}

export const dropdowns = (wrapper) =>
  wrapper.findAll('.agent-configuration .dropdown')

export async function choose(dropdown, text) {
  await dropdown.get('.dropdown__selected').trigger('click')
  await dropdown
    .findAll('.select__item-link')
    .find((item) => item.text().includes(text))
    .trigger('click')
}

export const fieldError = (wrapper, index) =>
  wrapper
    .findAll('.agent-configuration__body .control')
    [index].find('.control__messages--error')
