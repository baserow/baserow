import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { defineComponent, h, markRaw } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentConfigurationSidebar from '@baserow/modules/agent/components/AgentConfigurationSidebar'
import AgentInstructionsSection from '@baserow/modules/agent/components/configuration/AgentInstructionsSection'
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
      'agent.agentSettings',
      'agent.triggers',
      'agentChannels.section',
      'agentPermissions.section',
      'Plugin settings',
      'agent.workspaceAccess',
      'agent.actions',
      'agent.connectedApps',
    ])
    expect(
      wrapper
        .findAll('.agent-configuration__group-title')
        .map((title) => title.text())
    ).toEqual([
      'agent.groupEssentials',
      'agent.groupStart',
      'agent.groupCapabilities',
    ])
    expect(sections[5].get('.icon--error').attributes('aria-label')).toBe(
      'agent.fieldError'
    )
    expect(
      sections.every((section) => section.attributes('type') === 'button')
    ).toBe(true)

    await sections[5].trigger('click')
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
    expect(wrapper.findAll('.menu-list__item-button')).toHaveLength(9)
    const close = wrapper.get('button[aria-label="action.close"]')
    expect(close.attributes('type')).toBe('button')
    await close.trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  test('lists a section of an unknown group in the last group', async () => {
    class UnknownGroupSectionType extends PluginConfigurationSectionType {
      get group() {
        return 'unknown'
      }
    }
    testApp
      .getRegistry()
      .register(
        'agentConfigurationSection',
        new UnknownGroupSectionType({ app: testApp.getApp() })
      )
    const wrapper = await mountSidebar()

    expect(
      wrapper
        .findAll('.agent-configuration__group')
        .at(-1)
        .findAll('.menu-list__item-label')
        .map((label) => label.text())
    ).toContain('Plugin settings')
  })

  test('shows the section layout as a skeleton while loading', async () => {
    const wrapper = await mountSidebar({ loading: true })

    expect(wrapper.get('aside').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('.skeleton').attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('.agent-configuration__skeleton-row')).toHaveLength(
      8
    )
    expect(wrapper.findAll('.agent-configuration__group')).toHaveLength(3)
    expect(wrapper.findAll('.skeleton-block')).toHaveLength(27)
    expect(wrapper.find('.menu-list__item-button').exists()).toBe(false)
  })

  describe('suggested messages', () => {
    const mountInstructions = (extra = {}) =>
      testApp.mount(AgentInstructionsSection, {
        props: {
          configuration: completeConfiguration({
            suggested_messages: ['What can you do?'],
          }),
          errors: {},
          sectionType: testApp
            .getRegistry()
            .get('agentConfigurationSection', 'instructions'),
          editable: true,
          ...extra,
        },
      })
    const addButton = (wrapper) =>
      wrapper.find('.agent-suggested-messages__add')
    const rowInputs = (wrapper) =>
      wrapper.findAll('.agent-suggested-messages__item input')

    test('emits the trimmed list and leaves blank rows out', async () => {
      const wrapper = await mountInstructions()

      await addButton(wrapper).trigger('click')
      expect(rowInputs(wrapper)[1].element.labels[0].textContent).toContain(
        'agent.suggestedMessageLabel'
      )
      expect(document.activeElement).toBe(rowInputs(wrapper)[1].element)
      await rowInputs(wrapper)[1].setValue('  Summarize my week ')
      await addButton(wrapper).trigger('click')
      await rowInputs(wrapper)[2].setValue(' ')
      await rowInputs(wrapper)[2].trigger('blur')
      expect(rowInputs(wrapper)).toHaveLength(2)
      await wrapper
        .findAll('button[aria-label="agent.removeSuggestedMessage"]')[0]
        .trigger('click')

      expect(wrapper.emitted('change')).toEqual([
        [{ suggested_messages: ['What can you do?', 'Summarize my week'] }],
        [{ suggested_messages: ['What can you do?', 'Summarize my week'] }],
        [{ suggested_messages: ['Summarize my week'] }],
      ])
      expect(wrapper.emitted('flush')).toHaveLength(3)
    })

    test('hides Add once there are four messages', async () => {
      const wrapper = await mountInstructions({
        configuration: completeConfiguration({
          suggested_messages: ['One', 'Two', 'Three'],
        }),
      })

      await addButton(wrapper).trigger('click')

      expect(rowInputs(wrapper)).toHaveLength(4)
      expect(addButton(wrapper).exists()).toBe(false)
    })

    test('shows the messages read-only without buttons', async () => {
      const wrapper = await mountInstructions({ editable: false })

      expect(rowInputs(wrapper)[0].element.disabled).toBe(true)
      expect(addButton(wrapper).exists()).toBe(false)
      expect(
        wrapper
          .find('button[aria-label="agent.removeSuggestedMessage"]')
          .exists()
      ).toBe(false)
    })
  })
})
