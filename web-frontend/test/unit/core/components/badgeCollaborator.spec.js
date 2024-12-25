import { shallowMount } from '@vue/test-utils'
import BadgeCollaborator from '@baserow/modules/core/components/BadgeCollaborator'

describe('BadgeCollaborator.vue', () => {
  it('renders slot content', () => {
    const wrapper = shallowMount(BadgeCollaborator, {
      slots: {
        default: 'Roger Federer',
      },
    })
    expect(wrapper.find('.badge-collaborator__label').text()).toBe(
      'Roger Federer'
    )
  })

  it('displays initials when provided', () => {
    const wrapper = shallowMount(BadgeCollaborator, {
      propsData: {
        initials: 'RF',
      },
    })
    expect(wrapper.findComponent({ name: 'Avatar' }).props('initials')).toBe(
      'RF'
    )
  })

  it('shows remove icon when removeIcon is true', () => {
    const wrapper = shallowMount(BadgeCollaborator, {
      propsData: {
        removeIcon: true,
      },
    })
    expect(wrapper.find('.badge-collaborator__remove-icon').exists()).toBe(true)
  })

  it('emits remove event when remove icon is clicked', async () => {
    const wrapper = shallowMount(BadgeCollaborator, {
      propsData: {
        removeIcon: true,
      },
    })
    await wrapper.find('.badge-collaborator__remove-icon').trigger('click')
    expect(wrapper.emitted().remove).toBeTruthy()
  })

  it('applies correct class based on size prop', () => {
    const wrapper = shallowMount(BadgeCollaborator, {
      propsData: {
        size: 'small',
      },
    })
    expect(wrapper.classes()).toContain('badge-collaborator--small')
  })
})
