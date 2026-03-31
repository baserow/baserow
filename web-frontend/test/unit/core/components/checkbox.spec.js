import { mount } from '@vue/test-utils'
import Checkbox from '@baserow/modules/core/components/Checkbox.vue'

describe('Checkbox', () => {
  it('emits an input event when clicked', async () => {
    const wrapper = mount(Checkbox, {
      propsData: {
        checked: false,
      },
    })

    await wrapper.find('input[type="checkbox"]').setValue(true)

    expect(wrapper.emitted('input')).toBeTruthy()
    expect(wrapper.emitted('input')[0]).toEqual([true])
  })

  it('does not emit an input event when clicked and disabled', async () => {
    const wrapper = mount(Checkbox, {
      propsData: {
        checked: false,
        disabled: true,
      },
    })

    await wrapper.trigger('click')

    expect(wrapper.emitted('input')).toBeFalsy()
  })

  it('renders an indeterminate state when indeterminate and checkes props are true', () => {
    const wrapper = mount(Checkbox, {
      propsData: {
        indeterminate: true,
        checked: true,
      },
    })

    expect(wrapper.find('.checkbox__tick-indeterminate').exists()).toBe(true)
  })

  it('renders an error state when error prop is true', () => {
    const wrapper = mount(Checkbox, {
      propsData: {
        error: true,
      },
    })

    expect(wrapper.find('.checkbox--error').exists()).toBe(true)
  })
})
