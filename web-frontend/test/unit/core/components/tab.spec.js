import { mount } from '@vue/test-utils'
import Tab from '@baserow/modules/core/components/Tab'

describe('Tab.vue', () => {
  it('renders the tab content when isActive is true', async () => {
    const wrapper = await mount(Tab, {
      data() {
        return {
          isActive: true,
        }
      },
      slots: {
        default: 'Test Content',
      },
    })

    expect(wrapper.text()).toContain('Test Content')
  })

  it('does not render the tab content when isActive is false', async () => {
    const wrapper = await mount(Tab, {
      data() {
        return {
          isActive: false,
        }
      },
      slots: {
        default: 'Test Content',
      },
    })

    expect(wrapper.text()).not.toContain('Test Content')
  })
})
