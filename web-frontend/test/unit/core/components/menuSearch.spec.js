import { mount } from '@vue/test-utils'

import MenuSearch from '@baserow/modules/core/components/MenuSearch'

const mountComponent = (props = {}, options = {}) =>
  mount(MenuSearch, {
    props,
    global: {
      mocks: {
        $t: (key) => key,
      },
    },
    ...options,
  })

describe('MenuSearch', () => {
  test('emits model and keyboard updates', async () => {
    const wrapper = mountComponent({ placeholder: 'Search actions' })
    const input = wrapper.find('.menu-search__input')

    expect(input.attributes('placeholder')).toBe('Search actions')

    await input.setValue('row')
    await input.trigger('keydown', { key: 'ArrowDown' })

    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['row'])
    expect(wrapper.emitted('keydown')[0][0].key).toBe('ArrowDown')
  })

  test('clears the value and restores input focus', async () => {
    let wrapper
    wrapper = mountComponent(
      {
        modelValue: 'row',
        'onUpdate:modelValue': (value) =>
          wrapper.setProps({ modelValue: value }),
      },
      { attachTo: document.body }
    )

    const input = wrapper.find('.menu-search__input')
    const resetButton = wrapper.find('.menu-search__reset')

    expect(resetButton.attributes('aria-label')).toBe('dropdown.clearSearch')

    await resetButton.trigger('click')

    expect(wrapper.props('modelValue')).toBe('')
    expect(document.activeElement).toBe(input.element)
    expect(wrapper.find('.menu-search__reset').exists()).toBe(false)

    wrapper.unmount()
  })
})
