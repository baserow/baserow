import { mount } from '@vue/test-utils'
import Context from '@baserow/modules/core/components/Context'

describe('Context.vue', () => {
  it('renders the slot content when openedOnce is true', () => {
    const wrapper = mount(Context, {
      data() {
        return {
          openedOnce: true,
        }
      },
      slots: {
        default: 'Test Content',
      },
    })

    expect(wrapper.text()).toContain('Test Content')
  })

  it('does not render the slot content when openedOnce is false', () => {
    const wrapper = mount(Context, {
      data() {
        return {
          openedOnce: false,
        }
      },
      slots: {
        default: 'Test Content',
      },
    })

    expect(wrapper.text()).not.toContain('Test Content')
  })

  it('adds the visibility-hidden class when open or updatedOnce is false', () => {
    const wrapper = mount(Context, {
      data() {
        return {
          open: false,
          updatedOnce: false,
        }
      },
    })

    const contextEl = wrapper.find('[ref="contextEl"]').exists()
      ? wrapper.find('[ref="contextEl"]')
      : wrapper.find('.context')
    expect(contextEl.classes()).toContain('visibility-hidden')
  })

  it('does not add the visibility-hidden class when open and updatedOnce are true', () => {
    const wrapper = mount(Context, {
      data() {
        return {
          open: true,
          updatedOnce: true,
        }
      },
    })

    const contextEl = wrapper.find('.context')
    expect(contextEl.classes()).not.toContain('visibility-hidden')
  })

  it('adds the context--overflow-scroll class when overflowScroll prop is true', () => {
    const wrapper = mount(Context, {
      propsData: {
        overflowScroll: true,
      },
    })

    const contextEl = wrapper.find('.context')
    expect(contextEl.classes()).toContain('context--overflow-scroll')
  })

  it('does not add the context--overflow-scroll class when overflowScroll prop is false', () => {
    const wrapper = mount(Context, {
      propsData: {
        overflowScroll: false,
      },
    })

    const contextEl = wrapper.find('.context')
    expect(contextEl.classes()).not.toContain('context--overflow-scroll')
  })

  it('sets the correct default props', () => {
    const wrapper = mount(Context)

    expect(wrapper.props('hideOnClickOutside')).toBe(true)
    expect(wrapper.props('overflowScroll')).toBe(false)
    expect(typeof wrapper.props('maxHeightIfOutsideViewport')).toBe('boolean')
    expect(wrapper.props('maxHeightIfOutsideViewport')).toBe(false)
  })

  it('toggles the open state when the toggle method is called', async () => {
    const wrapper = mount(Context)
    const target = document.createElement('div')

    expect(wrapper.vm.open).toBe(false)

    wrapper.vm.toggle(target)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.open).toBe(true)
  })

  it('sets the opener when the toggle method is called with a target', async () => {
    const wrapper = mount(Context)
    const target = document.createElement('div')

    expect(wrapper.vm.opener).toBe(null)

    wrapper.vm.toggle(target)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.opener).toBe(target)
  })
})
