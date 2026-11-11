import { mount } from '@vue/test-utils'
import BadgeCounter from '@baserow/modules/core/components/BadgeCounter'

describe('BadgeCounter.vue', () => {
  it('renders count correctly', () => {
    const wrapper = mount(BadgeCounter, {
      propsData: {
        count: 5,
      },
    })

    expect(wrapper.text()).toBe('5')
  })

  it('renders limit correctly', () => {
    const wrapper = mount(BadgeCounter, {
      propsData: {
        count: 15,
        limit: 10,
      },
    })

    expect(wrapper.text()).toBe('9+')
  })

  it('hasOneDigitOnly computed property works correctly', () => {
    const wrapper = mount(BadgeCounter, {
      propsData: {
        count: 5,
      },
    })

    expect(wrapper.vm.hasOneDigitOnly).toBe(true)
  })
})
