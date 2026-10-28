import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { defineComponent, h, markRaw } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import { AgentConfigurationSectionType } from '@baserow/modules/agent/configurationSectionTypes'
import { completeConfiguration } from './helpers'

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

describe('Agent configuration sections', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    testApp.getRegistry().unregister('agentConfigurationSection', 'plugin')
    await testApp.afterEach()
  })

  const mountSidebar = (extra = {}) =>
    testApp.mount(AgentConfigurationSidebar, {
      props: {
        name: 'Support agent',
        configuration: completeConfiguration(),
        errors: {},
        enabledModels: { openai: ['model-one'] },
        editable: true,
        ...extra,
      },
    })

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
      'agent.workspaceAccess',
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
    expect(wrapper.findAll('.menu-list__item-button')).toHaveLength(4)
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
      3
    )
    expect(wrapper.findAll('.skeleton-block')).toHaveLength(9)
    expect(wrapper.find('.menu-list__item-button').exists()).toBe(false)
  })
})
