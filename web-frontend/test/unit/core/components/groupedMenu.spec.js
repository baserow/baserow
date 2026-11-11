import { mount } from '@vue/test-utils'

import GroupedMenu from '@baserow/modules/core/components/GroupedMenu'

const item = (id, label, extra = {}) => ({ id, label, value: id, ...extra })

// Groups without an `order` sort alphabetically; an ordered group goes after
// them, which is how the automation add-node menu lists its "Recipes" last.
const groups = [
  { id: 'zebra', label: 'Zebra', children: [item('z1', 'Zebra one')] },
  {
    id: 'recipes',
    label: 'Recipes',
    order: 1,
    children: [item('r1', 'While loop', { aliases: ['until'] })],
  },
  { id: 'apple', label: 'apple', children: [item('a1', 'Apple one')] },
]

const mountComponent = (props = {}) =>
  mount(GroupedMenu, {
    props: {
      items: groups,
      ...props,
    },
    global: {
      directives: {
        autoOverflowScroll: {},
        tooltip: {},
      },
      mocks: {
        $t: (key) => key,
      },
    },
  })

const navigationLabels = (wrapper) =>
  wrapper
    .findAll('.grouped-menu__navigation .menu-list__item-label')
    .map((element) => element.text())
const actionLabels = (wrapper) =>
  wrapper
    .findAll('.grouped-menu__actions .menu-list__item-label')
    .map((element) => element.text())

describe('GroupedMenu', () => {
  test('lists groups alphabetically, with ordered groups after the rest', () => {
    const wrapper = mountComponent()

    expect(navigationLabels(wrapper)).toEqual(['apple', 'Zebra', 'Recipes'])
    expect(actionLabels(wrapper)).toEqual(['Apple one'])
  })

  test('keeps that order while a search narrows the groups', async () => {
    const wrapper = mountComponent()
    const searchInput = wrapper.find('.menu-search__input')

    await searchInput.setValue('one')

    expect(navigationLabels(wrapper)).toEqual(['apple', 'Zebra'])

    await searchInput.setValue('until')

    expect(navigationLabels(wrapper)).toEqual(['Recipes'])
    expect(actionLabels(wrapper)).toEqual(['While loop'])
  })

  test('selects an item of an ordered group', async () => {
    const wrapper = mountComponent()

    await wrapper
      .findAll('.grouped-menu__navigation .menu-list__item-button')
      .find((element) => element.text().includes('Recipes'))
      .trigger('click')
    await wrapper
      .findAll('.grouped-menu__actions .menu-list__item-button')
      .find((element) => element.text().includes('While loop'))
      .trigger('click')

    expect(wrapper.emitted('select')[0][0].value).toBe('r1')
  })
})
