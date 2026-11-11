import { shallowMount } from '@vue/test-utils'
import Chips from '@baserow/modules/core/components/Chips'

describe('Chips.vue', () => {
  it('renders correctly when active', () => {
    const wrapper = shallowMount(Chips, {
      propsData: {
        active: true,
      },
    })

    expect(wrapper.classes()).toContain('chips--active')
  })

  it('renders correctly when not active', () => {
    const wrapper = shallowMount(Chips, {
      propsData: {
        active: false,
      },
    })

    expect(wrapper.classes()).not.toContain('chips--active')
  })

  it('renders the small size', () => {
    const wrapper = shallowMount(Chips, { propsData: { size: 'small' } })
    expect(wrapper.classes()).toContain('chips--small')
    expect(shallowMount(Chips).classes()).not.toContain('chips--small')
  })

  it('renders chips text in slot', () => {
    const text = 'Click me'
    const wrapper = shallowMount(Chips, {
      slots: {
        default: text,
      },
    })
    expect(wrapper.find('button').text()).toMatch(text)
  })

  it('emits click event when clicked', () => {
    const wrapper = shallowMount(Chips)
    wrapper.vm.$emit('click')
    expect(wrapper.emitted().click).toBeTruthy()
  })
})
