import { mountSuspended } from '@nuxt/test-utils/runtime'
import NoteIndicator from '@baserow/modules/core/components/NoteIndicator'
import MarkdownContext from '@baserow/modules/core/components/MarkdownContext'

const mountIndicator = (props, attrs = {}) =>
  mountSuspended(NoteIndicator, { props, attrs })

describe('NoteIndicator', () => {
  test('renders nothing without a note', async () => {
    const wrapper = await mountIndicator({ note: '' })

    expect(wrapper.find('.note-indicator').exists()).toBe(false)
    expect(wrapper.findComponent(MarkdownContext).exists()).toBe(false)
  })

  test('shows the icon and passes the note to the popover', async () => {
    const wrapper = await mountIndicator(
      { note: 'Why **this** step' },
      { class: 'custom-class' }
    )

    expect(wrapper.find('.note-indicator').classes()).toContain('custom-class')
    expect(wrapper.findComponent(MarkdownContext).props('content')).toBe(
      'Why **this** step'
    )
  })

  test('is a button, so it is reachable with the keyboard', async () => {
    const wrapper = await mountIndicator({ note: 'Read me' })

    const button = wrapper.find('.note-indicator')
    expect(button.element.tagName).toBe('BUTTON')
    expect(button.attributes('type')).toBe('button')
  })

  test('emits open when clicked', async () => {
    const wrapper = await mountIndicator({ note: 'Read me' })

    await wrapper.find('.note-indicator').trigger('click')

    expect(wrapper.emitted('open')).toHaveLength(1)
  })
})
