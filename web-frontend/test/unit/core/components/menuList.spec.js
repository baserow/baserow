import { mount } from '@vue/test-utils'

import MenuList from '@baserow/modules/core/components/MenuList'

const items = [
  {
    id: 'repeat',
    label: 'Repeat',
    value: 'repeat',
    icon: 'iconoir-repeat',
    description: 'Runs actions multiple times.',
    aliases: ['loop'],
  },
  {
    id: 'get-row',
    label: 'Get row',
    value: 'get-row',
    description: 'Reads a row from a table.',
  },
]

const mountComponent = (props = {}) =>
  mount(MenuList, {
    props: {
      items,
      ...props,
    },
    global: {
      directives: {
        autoOverflowScroll: {},
        tooltip: {},
      },
    },
  })

describe('MenuList', () => {
  test('renders a flat list and selects an item', async () => {
    const wrapper = mountComponent()

    expect(
      wrapper.findAll('.menu-list__item-label').map((item) => item.text())
    ).toEqual(['Repeat', 'Get row'])

    await wrapper
      .findAll('.menu-list__item-button')
      .find((item) => item.text().includes('Get row'))
      .trigger('click')

    expect(wrapper.emitted('select')[0][0].value).toBe('get-row')
  })

  test('filters flat items using labels, descriptions, and aliases', async () => {
    const wrapper = mountComponent({
      searchable: true,
      searchPlaceholder: 'Search actions',
    })

    await wrapper.find('.menu-list__search-input').setValue('loop')

    expect(
      wrapper.findAll('.menu-list__item-label').map((item) => item.text())
    ).toEqual(['Repeat'])
  })

  test('can hide item descriptions', () => {
    const wrapper = mountComponent({ showDescriptions: false })

    expect(wrapper.find('.menu-list__item-description').exists()).toBe(false)
  })

  test('emits disabled-click without selecting a disabled item', async () => {
    const wrapper = mountComponent({
      items: [
        {
          id: 'disabled',
          label: 'Disabled action',
          value: 'disabled',
          disabled: true,
          disabledReason: 'Upgrade required',
        },
      ],
    })

    await wrapper.find('.menu-list__item-button').trigger('click')

    expect(wrapper.emitted('disabled-click')[0][0].value).toBe('disabled')
    expect(wrapper.emitted('select')).toBeUndefined()
  })

  test('emits close when Escape is pressed', async () => {
    const wrapper = mountComponent()

    await wrapper.find('.menu-list').trigger('keydown', { key: 'Escape' })

    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
