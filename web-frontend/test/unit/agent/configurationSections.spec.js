import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h, markRaw, ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import { clone } from '@baserow/modules/core/utils/object'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import { AgentConfigurationSectionType } from '@baserow/modules/agent/configurationSectionTypes'
import {
  agentData,
  completeConfiguration,
  periodicTrigger,
  workspace,
} from './helpers'

const PluginSection = markRaw(
  defineComponent({
    inheritAttrs: false,
    props: { configuration: { type: Object, required: true } },
    emits: ['change', 'flush'],
    setup(props, { emit }) {
      return () =>
        h('input', {
          'aria-label': 'Plugin option',
          value: props.configuration.plugin_option,
          onInput: (event) =>
            emit('change', { plugin_option: event.target.value }),
          onBlur: () => emit('flush'),
        })
    },
  })
)

class PluginConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'plugin'
  }

  get name() {
    return 'Plugin settings'
  }

  get description() {
    return 'Additional plugin configuration.'
  }

  get icon() {
    return 'iconoir-settings'
  }

  get component() {
    return PluginSection
  }

  get fields() {
    return { plugin_option: { label: 'Plugin option' } }
  }

  getOrder() {
    return 15
  }
}

class TriggerAwareSectionType extends PluginConfigurationSectionType {
  constructor(context, contexts) {
    super(context)
    this.contexts = contexts
  }

  setup(context) {
    this.contexts.push(context)
  }

  getErrorMessage(errors, configuration, { triggers }) {
    return triggers.loaded && !triggers.triggers.some(({ enabled }) => enabled)
      ? 'No enabled trigger'
      : ''
  }
}

describe('Agent configuration sections', () => {
  let testApp, agent

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', clone(workspace))
    agent = await testApp.store.dispatch(
      'application/forceCreate',
      clone(agentData)
    )
  })

  afterEach(async () => {
    testApp.getRegistry().unregister('agentConfigurationSection', 'plugin')
    await testApp.afterEach()
  })

  const sectionCount = () =>
    testApp.getRegistry().getOrderedList('agentConfigurationSection').length

  const mountSidebar = (extra = {}, triggers = []) => {
    testApp.mock.onGet('/agent/10/triggers/').reply(200, triggers)
    testApp.mock.onGet('/agent/10/trigger-types/').reply(200, [])
    return testApp.mount(AgentConfigurationSidebar, {
      props: {
        name: 'Support agent',
        configuration: completeConfiguration({
          available_trigger_types: ['periodic'],
        }),
        errors: {},
        enabledModels: { openai: ['model-one'] },
        editable: true,
        ...extra,
      },
      global: { provide: { agentApplication: ref(agent) } },
    })
  }

  test('renders registered sections in order with their form and validation', async () => {
    testApp
      .getRegistry()
      .register(
        'agentConfigurationSection',
        new PluginConfigurationSectionType({ app: testApp.getApp() })
      )
    const wrapper = await mountSidebar({
      configuration: completeConfiguration({ plugin_option: 'Existing value' }),
      errors: { plugin_option: 'required' },
    })
    const sections = wrapper.findAll('.menu-list__item-button')

    expect(
      sections.map((section) => section.get('.menu-list__item-label').text())
    ).toEqual([
      'agent.instructions',
      'Plugin settings',
      'agent.whenItRuns',
      'agent.workspaceAccess',
      'agentPermissions.section',
      'agent.actions',
      'agent.connectedApps',
      'agent.agentSettings',
    ])
    expect(sections[1].get('.icon--error').attributes('aria-label')).toBe(
      'agent.fieldError'
    )
    expect(
      sections.every((section) => section.attributes('type') === 'button')
    ).toBe(true)

    await sections[1].trigger('click')
    expect(wrapper.get('h2').text()).toBe('Plugin settings')
    const input = wrapper.get('input[aria-label="Plugin option"]')
    expect(input.element.value).toBe('Existing value')

    await input.setValue('Updated value')
    await input.trigger('blur')
    expect(wrapper.emitted('change')).toEqual([
      [{ plugin_option: 'Updated value' }],
    ])
    expect(wrapper.emitted('flush')).toHaveLength(1)

    const back = wrapper.get('button[aria-label="action.back"]')
    expect(back.attributes('type')).toBe('button')
    await back.trigger('click')
    expect(wrapper.findAll('.menu-list__item-button')).toHaveLength(
      sectionCount()
    )
    const close = wrapper.get('button[aria-label="action.close"]')
    expect(close.attributes('type')).toBe('button')
    await close.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  test('shows the section layout as a skeleton while loading', async () => {
    const wrapper = await mountSidebar({ loading: true })

    expect(wrapper.get('aside').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('.skeleton').attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('.agent-configuration__skeleton-row')).toHaveLength(
      sectionCount()
    )
    expect(wrapper.findAll('.skeleton-block')).toHaveLength(sectionCount() * 3)
    expect(wrapper.find('.menu-list__item-button').exists()).toBe(false)
  })

  test('gives sections the agent, its workspace and its triggers, loaded once with the sidebar', async () => {
    const contexts = []
    testApp
      .getRegistry()
      .register(
        'agentConfigurationSection',
        new TriggerAwareSectionType({ app: testApp.getApp() }, contexts)
      )
    testApp.mock.onPatch('/agent/10/triggers/1/').reply(200, periodicTrigger())
    const wrapper = await mountSidebar({}, [
      periodicTrigger({ enabled: false }),
    ])
    const item = (label) =>
      wrapper
        .findAll('.menu-list__item-button')
        .find((button) => button.text().includes(label))
    const triggerLoads = () =>
      testApp.mock.history.get.filter(
        ({ url }) => url === '/agent/10/triggers/'
      )

    expect(contexts).toHaveLength(1)
    expect(contexts[0].agent.id).toBe(10)
    expect(contexts[0].workspace.id).toBe(1)
    expect(item('Plugin settings').get('.icon--error').attributes()).toEqual(
      expect.objectContaining({ 'aria-label': 'No enabled trigger' })
    )

    await item('agent.whenItRuns').trigger('click')
    expect(wrapper.find('.skeleton').exists()).toBe(false)
    await wrapper.get('.agent-trigger-card__switch').trigger('click')
    await flushPromises()
    await wrapper.get('button[aria-label="action.back"]').trigger('click')

    expect(item('Plugin settings').find('.icon--error').exists()).toBe(false)
    expect(triggerLoads()).toHaveLength(1)
    expect(contexts).toHaveLength(1)
  })
})
