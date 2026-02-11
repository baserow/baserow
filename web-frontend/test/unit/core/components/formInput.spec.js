import { mountSuspended } from '@nuxt/test-utils/runtime'

import FormInput from '@baserow/modules/core/components/FormInput.vue'

describe('FormInput.vue', () => {
  it('renders the input with the correct attributes when props are provided', async () => {
    const wrapper = await mountSuspended(FormInput, {
      props: {
        type: 'text',
        disabled: true,
        monospace: true,
        loading: true,
        iconLeft: 'iconoir-user',
        iconRight: 'iconoir-search',
        required: true,
      },
    })

    expect(wrapper.find('.form-input__input').attributes('type')).toBe('text')
    expect(
      wrapper.find('.form-input__input').attributes('disabled')
    ).toBeDefined()
    expect(wrapper.find('.form-input').classes()).toContain(
      'form-input--monospace'
    )
    expect(wrapper.find('.form-input__icon-left').classes()).toContain(
      'iconoir-user'
    )
    expect(wrapper.find('.form-input__icon-right').classes()).toContain(
      'iconoir-search'
    )
    expect(wrapper.find('.form-input').classes()).toContain(
      'form-input--disabled'
    )
    expect(wrapper.find('.form-input').classes()).toContain(
      'form-input--monospace'
    )
    expect(wrapper.find('.form-input').classes()).toContain(
      'form-input--loading'
    )
    expect(wrapper.find('.control__required').exists()).toBe(false)
  })

  it('emits the "input" event when the input value changes', async () => {
    const wrapper = await mountSuspended(FormInput, {
      propsData: { label: 'Name', type: 'text' },
    })
    const inputElement = wrapper.find('.form-input__input')
    inputElement.setValue('John Doe')
    expect(wrapper.emitted('input')[0]).toEqual(['John Doe'])
  })
})
