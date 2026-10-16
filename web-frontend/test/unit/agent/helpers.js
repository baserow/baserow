import { vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
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

export const useFakeTimers = () =>
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })

export async function debounce() {
  await vi.advanceTimersByTimeAsync(400)
  await flushPromises()
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
