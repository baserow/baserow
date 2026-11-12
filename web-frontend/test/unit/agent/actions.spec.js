import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import AgentActionsSection from '@baserow/modules/agent/components/configuration/AgentActionsSection'
import AgentFormulaInput from '@baserow/modules/agent/components/configuration/AgentFormulaInput'
import { registerRealtimeEvents } from '@baserow/modules/agent/realtime'
import {
  agentData,
  workspace,
  completeConfiguration,
  useFakeTimers,
  choose,
  deferredReply,
} from './helpers'

const formula = (value = '') => ({
  formula: value,
  mode: 'simple',
  version: '0.1',
})
const emailAction = (extra = {}) => ({
  id: 1,
  type: 'smtp_email',
  name: 'send_email',
  description: 'Send an email to someone.',
  enabled: true,
  ask_first: false,
  inputs: [
    {
      id: '11111111-1111-4111-8111-111111111111',
      name: 'to_email',
      type: 'email',
      description: 'Recipient address.',
      required: true,
    },
    {
      id: '22222222-2222-4222-8222-222222222222',
      name: 'subject',
      type: 'string',
      description: 'Subject.',
      required: true,
    },
    {
      id: '33333333-3333-4333-8333-333333333333',
      name: 'body',
      type: 'string',
      description: 'Body.',
      required: true,
    },
  ],
  service: {
    id: 20,
    type: 'smtp_email',
    integration_id: null,
    use_instance_smtp_settings: false,
    instance_smtp_settings_enabled: true,
    from_email: formula(),
    from_name: formula(),
    cc_emails: formula(),
    bcc_emails: formula(),
    to_emails: formula(
      "get('tool_input.11111111-1111-4111-8111-111111111111')"
    ),
    subject: formula("get('tool_input.22222222-2222-4222-8222-222222222222')"),
    body: formula("get('tool_input.33333333-3333-4333-8333-333333333333')"),
    body_type: 'plain',
  },
  errors: { integration: 'required', from_email: 'required' },
  ...extra,
})
const patches = (app) =>
  app.mock.history.patch.map(({ url, data }) => [url, JSON.parse(data)])

/** These tests exercise the real editor/store/form host and its HTTP contract. */
describe('Agent action editor', () => {
  let testApp, agent, agentRef
  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', clone(workspace))
    agent = await testApp.store.dispatch(
      'application/forceCreate',
      clone(agentData)
    )
    agentRef = ref(agent)
    testApp.mock.onGet('application/10/integrations/').reply(200, [])
  })
  afterEach(async () => {
    await testApp.afterEach()
    vi.useRealTimers()
  })

  async function mountSection(items, editable = true, expand = true) {
    testApp.mock.onGet('/agent/10/actions/').reply(200, clone(items))
    const wrapper = await testApp.mount(AgentActionsSection, {
      props: {
        editable,
        configuration: completeConfiguration({
          available_action_types: ['smtp_email'],
        }),
      },
      global: { provide: { agentApplication: agentRef } },
    })
    await flushPromises()
    if (expand) {
      for (const toggle of wrapper.findAll('.agent-action-card__toggle'))
        await toggle.trigger('click')
      for (const toggle of wrapper.findAll('.agent-action-inputs__toggle'))
        await toggle.trigger('click')
    }
    return wrapper
  }
  function saveEdits(original = emailAction()) {
    let saved = clone(original)
    testApp.mock
      .onPatch(`/agent/10/actions/${original.id}/`)
      .reply(({ data }) => {
        const values = JSON.parse(data)
        saved = {
          ...saved,
          ...values,
          service: { ...saved.service, ...values.service },
        }
        return [200, clone(saved)]
      })
  }
  async function settle() {
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()
  }

  test('loads integrations and hosts the SMTP form with prepared input bindings, without an initial save', async () => {
    const wrapper = await mountSection([emailAction()])
    expect(
      wrapper.findComponent({ name: 'CoreSMTPEmailServiceForm' }).exists()
    ).toBe(true)
    expect(wrapper.findAll('.agent-action-inputs__item')).toHaveLength(3)
    expect(
      wrapper
        .findAll('[role="switch"]')
        .map((node) => node.attributes('aria-checked'))
    ).toEqual(['true', 'false'])
    expect(wrapper.findAllComponents(AgentFormulaInput)).toHaveLength(7)
    expect(wrapper.get('.agent-action-card').text()).toContain(
      'agent.actionMisconfigured'
    )
    expect(wrapper.get('.agent-action-card__service').text()).toContain(
      'to_email'
    )
    expect(patches(testApp)).toEqual([])
    expect(testApp.mock.history.get.map(({ url }) => url)).toContain(
      'application/10/integrations/'
    )
  })

  test('the shared picker creates only the requested type; the server owns defaults', async () => {
    testApp.mock.onPost('/agent/10/actions/').reply(200, emailAction())
    const wrapper = await mountSection([])
    await wrapper.get('.agent-actions__header button').trigger('click')
    await flushPromises()
    const email = wrapper
      .findAll('.grouped-menu__actions .menu-list__item-button')
      .find((node) => node.text().includes('serviceType.coreSMTPEmail'))
    expect(email).toBeTruthy()
    await email.trigger('click')
    await flushPromises()
    expect(
      testApp.mock.history.post.map(({ data }) => JSON.parse(data))
    ).toEqual([{ type: 'smtp_email' }])
    expect(wrapper.findAll('.agent-action-card')).toHaveLength(1)
    expect(wrapper.get('.agent-action-card__body').isVisible()).toBe(true)
    expect(patches(testApp)).toEqual([])
  })

  test('independent templates save names and approval switches to their own action', async () => {
    useFakeTimers()
    const first = emailAction()
    const second = emailAction({ id: 2, name: 'send_report' })
    saveEdits(first)
    saveEdits(second)
    const wrapper = await mountSection([first, second])
    const cards = wrapper.findAll('.agent-action-card')
    await cards[1]
      .get('.agent-action-card__body input')
      .setValue('send_summary')
    await cards[0]
      .findAll('[role="switch"]')[1]
      .trigger('keydown', { key: 'Enter' })
    await settle()
    expect(patches(testApp)).toEqual([
      ['/agent/10/actions/1/', { ask_first: true }],
      ['/agent/10/actions/2/', { name: 'send_summary' }],
    ])
    expect(cards[0].get('.agent-action-card__body input').element.value).toBe(
      'send_email'
    )
  })

  test('renaming and changing input types preserves IDs and formula bindings', async () => {
    useFakeTimers()
    saveEdits()
    const original = emailAction()
    const wrapper = await mountSection([original])
    const row = wrapper.get('.agent-action-inputs__item')
    await row.get('.agent-action-inputs__editor input').setValue('recipient')
    await choose(
      row.get('.agent-action-inputs__editor .dropdown'),
      'agent.actionInputTypestring'
    )
    await settle()
    const saved = patches(testApp)[0][1]
    expect(saved.inputs[0]).toEqual({
      ...original.inputs[0],
      name: 'recipient',
      type: 'string',
    })
    expect(saved).not.toHaveProperty('service')
    expect(wrapper.get('.agent-action-card__service').text()).toContain(
      'recipient'
    )
  })

  test('new input variables get unique stable IDs and names without changing existing bindings', async () => {
    useFakeTimers()
    saveEdits()
    const wrapper = await mountSection([emailAction()])
    await wrapper.get('.agent-action-inputs__header button').trigger('click')
    await wrapper.get('.agent-action-inputs__header button').trigger('click')
    await settle()
    const values = patches(testApp)[0][1]
    expect(values.inputs.slice(-2).map(({ name }) => name)).toEqual([
      'input',
      'input_2',
    ])
    expect(new Set(values.inputs.map(({ id }) => id)).size).toBe(5)
    expect(
      values.inputs.slice(-2).every(({ id }) => /^[0-9a-f-]{36}$/.test(id))
    ).toBe(true)
    expect(values).not.toHaveProperty('service')
  })

  test('new variables open for editing and referenced inputs can remain optional', async () => {
    useFakeTimers()
    saveEdits()
    const wrapper = await mountSection([emailAction()])
    await wrapper.get('.agent-action-inputs__header button').trigger('click')
    const rows = wrapper.findAll('.agent-action-inputs__item')
    expect(
      rows
        .at(-1)
        .get('.agent-action-inputs__toggle')
        .attributes('aria-expanded')
    ).toBe('true')
    expect(rows.at(-1).get('.agent-action-inputs__editor').isVisible()).toBe(
      true
    )
    const requirement = rows[0].get('.agent-action-inputs__requirement')
    expect(requirement.get('.dropdown__selected').text()).toBe(
      'agent.actionInputRequired'
    )
    expect(
      rows
        .at(-1)
        .get('.agent-action-inputs__requirement .dropdown__selected')
        .text()
    ).toBe('agent.actionInputRequired')
    await requirement.get('.dropdown__selected').trigger('click')
    await requirement.findAll('.select__item-link')[1].trigger('click')
    await settle()
    expect(patches(testApp)[0][1].inputs[0].required).toBe(false)
    expect(patches(testApp)[0][1]).not.toHaveProperty('service')
    expect(requirement.get('.dropdown__selected').text()).toBe(
      'agent.actionInputOptional'
    )
    await requirement.get('.dropdown__selected').trigger('click')
    await requirement.findAll('.select__item-link')[0].trigger('click')
    await settle()
    expect(patches(testApp)[1][1].inputs[0].required).toBe(true)
  })

  test('deleting a referenced input clears its formula in the same save and preserves other inputs', async () => {
    useFakeTimers()
    const action = emailAction({ errors: {} })
    saveEdits(action)
    const wrapper = await mountSection([action])
    await wrapper.get('.agent-action-inputs__delete').trigger('click')
    expect(wrapper.get('.agent-action-card__service').text()).not.toContain(
      'to_email'
    )
    await settle()
    const saved = patches(testApp)[0][1]
    expect(saved.inputs).toHaveLength(2)
    expect(saved.service).toEqual({ to_emails: formula() })
    expect(wrapper.get('.agent-action-card').text()).not.toContain(
      'agent.actionMisconfigured'
    )
    expect(wrapper.get('.agent-action-card__service').text()).toContain(
      'subject'
    )
  })

  test('cards and input editors collapse without losing unsaved values', async () => {
    useFakeTimers()
    saveEdits()
    const wrapper = await mountSection([emailAction()], true, false)
    const cardToggle = wrapper.get('.agent-action-card__toggle')
    expect(cardToggle.text()).toContain('send_email')
    expect(cardToggle.attributes('aria-expanded')).toBe('false')
    expect(wrapper.get('.agent-action-card__body').isVisible()).toBe(false)
    await cardToggle.trigger('click')
    expect(wrapper.get('.agent-action-card__approval').text()).toContain(
      'agent.actionAskFirstHelp'
    )
    const inputToggle = wrapper.get('.agent-action-inputs__toggle')
    expect(inputToggle.attributes('aria-expanded')).toBe('false')
    await inputToggle.trigger('click')
    await wrapper
      .get('.agent-action-inputs__editor input')
      .setValue('recipient')
    await inputToggle.trigger('click')
    await cardToggle.trigger('click')
    await wrapper.get('.agent-card-list__toggle-all').trigger('click')
    await inputToggle.trigger('click')
    expect(
      wrapper.get('.agent-action-inputs__editor input').element.value
    ).toBe('recipient')
    await settle()
    expect(patches(testApp)[0][1].inputs[0].name).toBe('recipient')
  })

  test('expand and collapse all affects every action while enable controls remain visible', async () => {
    const wrapper = await mountSection(
      [emailAction(), emailAction({ id: 2, name: 'send_report' })],
      true,
      false
    )
    const all = wrapper.get('.agent-card-list__toggle-all')
    await all.trigger('click')
    expect(
      wrapper
        .findAll('.agent-action-card__body')
        .every((body) => body.isVisible())
    ).toBe(true)
    await all.trigger('click')
    expect(
      wrapper
        .findAll('.agent-action-card__body')
        .every((body) => !body.isVisible())
    ).toBe(true)
    expect(
      wrapper
        .findAll('.agent-action-card__header [role="switch"]')
        .every((control) => control.isVisible())
    ).toBe(true)
  })

  test('failed edits stay visible and retry without restoring removed inputs', async () => {
    useFakeTimers()
    testApp.dontFailOnErrorResponses()
    const action = emailAction()
    testApp.mock.onPatch('/agent/10/actions/1/').replyOnce(400, {
      error: 'ERROR_REQUEST_BODY_VALIDATION',
      detail: { name: [{ error: 'Duplicate name.', code: 'invalid' }] },
    })
    saveEdits()
    const wrapper = await mountSection([action])
    await wrapper
      .get('.agent-action-card__body input')
      .setValue('send_duplicate')
    await settle()
    expect(wrapper.get('.agent-action-card__body input').element.value).toBe(
      'send_duplicate'
    )
    expect(wrapper.get('.agent-action-card__error').text()).toContain(
      'Duplicate name.'
    )
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'action.retry')
      .trigger('click')
    await flushPromises()
    expect(patches(testApp).map((entry) => entry[1])).toEqual([
      { name: 'send_duplicate' },
      { name: 'send_duplicate' },
    ])
    expect(wrapper.find('.agent-action-card__error').exists()).toBe(false)
  })

  test('late saves keep newer typing and serialize the follow-up save', async () => {
    useFakeTimers()
    const held = deferredReply()
    testApp.mock.onPatch('/agent/10/actions/1/').replyOnce(held.reply)
    saveEdits()
    const wrapper = await mountSection([emailAction()])
    const input = wrapper.get('.agent-action-card__body input')
    await input.setValue('send_first')
    await settle()
    await input.setValue('send_latest')
    await settle()
    expect(patches(testApp)).toHaveLength(1)
    held.resolve(200, emailAction({ name: 'send_first' }))
    await flushPromises()
    expect(input.element.value).toBe('send_latest')
    expect(patches(testApp).map((entry) => entry[1])).toEqual([
      { name: 'send_first' },
      { name: 'send_latest' },
    ])
  })

  test('switching agents drains the previous action draft without overwriting the new agent', async () => {
    useFakeTimers()
    const held = deferredReply()
    testApp.mock.onPatch('/agent/10/actions/1/').replyOnce(held.reply)
    saveEdits()
    const wrapper = await mountSection([emailAction()])
    const name = wrapper.get('.agent-action-card__body input')
    await name.setValue('first_edit')
    await settle()
    await name.setValue('last_edit')
    const otherAgent = await testApp.store.dispatch('application/forceCreate', {
      ...clone(agentData),
      id: 11,
    })
    testApp.mock.onGet('application/11/integrations/').reply(200, [])
    testApp.mock
      .onGet('/agent/11/actions/')
      .reply(200, [emailAction({ id: 2, name: 'other_agent_tool' })])
    agentRef.value = otherAgent
    await flushPromises()
    held.resolve(200, emailAction({ name: 'first_edit' }))
    await flushPromises()
    expect(patches(testApp)).toEqual([
      ['/agent/10/actions/1/', { name: 'first_edit' }],
      ['/agent/10/actions/1/', { name: 'last_edit' }],
    ])
    expect(wrapper.get('.agent-action-card__body input').element.value).toBe(
      'other_agent_tool'
    )
  })

  test('deleting an action does not delete the others', async () => {
    testApp.mock.onDelete('/agent/10/actions/1/').reply(204)
    const wrapper = await mountSection([
      emailAction(),
      emailAction({ id: 2, name: 'follow_up' }),
    ])
    await wrapper.get('.agent-action-card__footer button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.agent-action-card')).toHaveLength(1)
    expect(wrapper.get('.agent-action-card__body input').element.value).toBe(
      'follow_up'
    )
  })

  test('realtime changes update the current agent and preserve local drafts', async () => {
    useFakeTimers()
    saveEdits()
    const events = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => {
        events[name] = handler
      },
    })
    const wrapper = await mountSection([emailAction()])
    await wrapper.get('.agent-action-card__body input').setValue('draft_name')
    await events.agent_action_updated(
      { store: testApp.store },
      {
        agent_id: 10,
        action: emailAction({
          ask_first: true,
          service: {
            ...emailAction().service,
            subject: formula("'Remote subject'"),
          },
        }),
      }
    )
    await flushPromises()
    expect(wrapper.get('.agent-action-card__body input').element.value).toBe(
      'draft_name'
    )
    expect(
      wrapper.findAll('[role="switch"]')[1].attributes('aria-checked')
    ).toBe('true')
    expect(wrapper.get('.agent-action-card__service').text()).toContain(
      'Remote subject'
    )
    await events.agent_action_deleted(
      { store: testApp.store },
      { agent_id: 10, action_id: 1 }
    )
    await flushPromises()
    expect(wrapper.find('.agent-action-card').exists()).toBe(false)
    await settle()
    expect(patches(testApp)).toEqual([])
  })

  test('read-only configuration has no editing or deleting actions', async () => {
    const wrapper = await mountSection([emailAction()], false)
    expect(wrapper.find('.agent-actions__header button').exists()).toBe(false)
    expect(wrapper.find('.agent-action-card__footer').exists()).toBe(false)
    expect(wrapper.find('.agent-action-inputs__delete').exists()).toBe(false)
    expect(
      wrapper.get('.agent-action-card__body input').attributes('disabled')
    ).toBeDefined()
    expect(
      wrapper
        .findAll('[role="switch"]')
        .every((node) => node.attributes('aria-disabled') === 'true')
    ).toBe(true)
  })

  test('formula schema uses immutable IDs and readable titles without inventing values', () => {
    const provider = testApp
      .getRegistry()
      .get('agentDataProvider', 'tool_input')
    const action = emailAction()
    const schema = provider.getDataSchema({ action })
    expect(Object.keys(schema.properties)).toEqual(
      action.inputs.map((input) => input.id)
    )
    expect(schema.properties[action.inputs[0].id]).toMatchObject({
      type: 'string',
      title: 'to_email',
    })
    action.inputs[0].name = 'recipient'
    expect(
      provider.getDataSchema({ action }).properties[action.inputs[0].id].title
    ).toBe('recipient')
    action.inputs.splice(0, 1)
    expect(provider.getDataSchema({ action }).properties).not.toHaveProperty(
      '11111111-1111-4111-8111-111111111111'
    )
  })
})
