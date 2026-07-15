import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'

import GroupedDropdown from '@baserow/modules/core/components/GroupedDropdown'

const ContextStub = defineComponent({
  name: 'Context',
  emits: ['shown', 'hidden'],
  methods: {
    show() {
      this.$emit('shown')
    },
    hide() {
      this.$emit('hidden')
    },
  },
  template: '<div class="context-stub"><slot /></div>',
})

const items = [
  {
    id: 'local-baserow',
    label: 'Local Baserow',
    image: '/local-baserow.svg',
    children: [
      { id: 'get-row', label: 'Get row', value: 'get-row' },
      { id: 'list-rows', label: 'List rows', value: 'list-rows' },
    ],
  },
]

const mountComponent = (props = {}) =>
  mount(GroupedDropdown, {
    props: {
      items,
      placeholder: 'Choose action...',
      ...props,
    },
    global: {
      mocks: {
        $t: (key) => key,
      },
      directives: {
        autoOverflowScroll: {},
        tooltip: {},
      },
      stubs: {
        Context: ContextStub,
      },
    },
  })

describe('GroupedDropdown', () => {
  test('uses the ancestor image for the selected leaf', () => {
    const wrapper = mountComponent({ modelValue: 'get-row' })

    expect(wrapper.find('.grouped-dropdown__menu--grouped').exists()).toBe(true)
    expect(wrapper.find('.dropdown__selected-text').text()).toBe('Get row')
    expect(wrapper.find('.dropdown__selected-image').attributes('src')).toBe(
      '/local-baserow.svg'
    )
  })

  test('selects a group action and emits v-model events', async () => {
    const wrapper = mountComponent()

    await wrapper.find('.grouped-dropdown__trigger').trigger('click')
    await wrapper
      .findAll('.grouped-dropdown__navigation .menu-list__item-button')
      .find((item) => item.text().includes('Local Baserow'))
      .trigger('click')
    await wrapper
      .findAll('.grouped-dropdown__actions .menu-list__item-button')
      .find((item) => item.text().includes('List rows'))
      .trigger('click')

    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['list-rows'])
    expect(wrapper.emitted('change')[0]).toEqual(['list-rows'])
    expect(wrapper.emitted('select')[0][0].label).toBe('List rows')
  })

  test('filters actions and hides groups without results', async () => {
    const wrapper = mountComponent({
      showSearch: true,
      emptyText: 'No actions found',
      items: [
        {
          id: 'local-baserow',
          label: 'Local Baserow',
          children: [
            {
              id: 'get-row',
              label: 'Get row',
              value: 'get-row',
              description: 'Reads a row from a table.',
            },
          ],
        },
        {
          id: 'slack',
          label: 'Slack',
          children: [
            {
              id: 'send-message',
              label: 'Send message',
              value: 'send-message',
              description: 'Sends a message to a channel.',
            },
          ],
        },
        {
          id: 'empty-integration',
          label: 'Empty integration',
          children: [],
        },
      ],
    })

    expect(
      wrapper
        .findAll('.grouped-dropdown__navigation .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Local Baserow', 'Slack'])
    expect(
      wrapper
        .findAll('.grouped-dropdown__actions .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Get row'])

    await wrapper.find('.menu-search__input').setValue('message')

    expect(
      wrapper
        .findAll('.grouped-dropdown__navigation .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Slack'])
    expect(
      wrapper
        .findAll('.grouped-dropdown__actions .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Send message'])

    await wrapper.find('.menu-search__input').setValue('missing')

    expect(wrapper.find('.grouped-dropdown__navigation').exists()).toBe(false)
    expect(wrapper.find('.grouped-dropdown__empty').text()).toBe(
      'No actions found'
    )
  })

  test('clears the search with the reset button', async () => {
    const wrapper = mountComponent({ showSearch: true })
    const searchInput = wrapper.find('.menu-search__input')

    expect(wrapper.find('.menu-search__reset').exists()).toBe(false)

    await searchInput.setValue('get')

    const resetButton = wrapper.find('.menu-search__reset')
    expect(resetButton.attributes('aria-label')).toBe('dropdown.clearSearch')

    await resetButton.trigger('click')

    expect(searchInput.element.value).toBe('')
    expect(wrapper.find('.menu-search__reset').exists()).toBe(false)
  })

  test('activates the group containing the selected value', () => {
    const wrapper = mountComponent({
      modelValue: 'get-row',
      items: [
        {
          id: 'slack',
          label: 'Slack',
          children: [
            {
              id: 'send-message',
              label: 'Send message',
              value: 'send-message',
            },
          ],
        },
        {
          id: 'local-baserow',
          label: 'Local Baserow',
          children: [{ id: 'get-row', label: 'Get row', value: 'get-row' }],
        },
      ],
    })

    expect(
      wrapper
        .find('.grouped-dropdown__navigation .menu-list__item-button--active')
        .text()
    ).toContain('Local Baserow')
    expect(
      wrapper
        .findAll('.grouped-dropdown__actions .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Get row'])
  })

  test('keeps disabled groups visible without activating them', () => {
    const wrapper = mountComponent({
      items: [
        {
          id: 'disabled-integration',
          label: 'Disabled integration',
          disabled: true,
          disabledReason: 'Configuration required',
          children: [
            {
              id: 'disabled-action',
              label: 'Disabled action',
              value: 'disabled-action',
            },
          ],
        },
        {
          id: 'available-integration',
          label: 'Available integration',
          children: [
            {
              id: 'available-action',
              label: 'Available action',
              value: 'available-action',
            },
          ],
        },
      ],
    })

    const navigationButtons = wrapper.findAll(
      '.grouped-dropdown__navigation .menu-list__item-button'
    )

    expect(navigationButtons.map((button) => button.text())).toEqual([
      'Disabled integration',
      'Available integration',
    ])
    expect(navigationButtons[0].attributes('aria-disabled')).toBe('true')
    expect(navigationButtons[0].classes()).not.toContain(
      'menu-list__item-button--active'
    )
    expect(navigationButtons[1].classes()).toContain(
      'menu-list__item-button--active'
    )
    expect(
      wrapper
        .findAll('.grouped-dropdown__actions .menu-list__item-label')
        .map((item) => item.text())
    ).toEqual(['Available action'])
  })

  test('renders flat dropdown items without a navigation panel', () => {
    const wrapper = mountComponent({
      items: [{ id: 'repeat', label: 'Repeat', value: 'repeat' }],
    })

    expect(wrapper.find('.grouped-dropdown__navigation').exists()).toBe(false)
    expect(wrapper.find('.menu-list__item-label').text()).toBe('Repeat')
  })
})
