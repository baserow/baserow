import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditFieldRichText from '@baserow/modules/database/components/row/RowEditFieldRichText'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'

describe('RowEditFieldRichText component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const field = {
    id: 1,
    name: 'Notes',
    order: 0,
    type: 'long_text',
    primary: false,
    long_text_enable_rich_text: true,
    _: { loading: false },
  }

  const mountComponent = (props = {}) =>
    testApp.mount(RowEditFieldRichText, {
      props: {
        field,
        value: '**bold** text',
        readOnly: false,
        workspaceId: 10,
        ...props,
      },
      global: {
        stubs: {
          RichTextEditorBubbleMenu: true,
          RichTextEditorFloatingMenu: true,
        },
      },
    })

  test('renders the stored Markdown value as rich content', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.find('.tiptap strong').text()).toBe('bold')
    expect(wrapper.find('.tiptap').attributes('contenteditable')).toBe('true')
  })

  test('saves the serialized Markdown on blur', async () => {
    const wrapper = await mountComponent()
    const editor = wrapper.findComponent(RichTextEditor)

    editor.vm.$emit('focus')
    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('update')
    expect(emitted).toHaveLength(1)
    const [newValue, oldValue] = emitted[0]
    expect(oldValue).toBe('**bold** text')
    expect(typeof newValue).toBe('string')
    expect(newValue).not.toBe(oldValue)
    expect(newValue).toContain('**bold**')
  })

  test('does not save when the content did not change', async () => {
    const wrapper = await mountComponent()
    const editor = wrapper.findComponent(RichTextEditor)

    editor.vm.$emit('focus')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('does not rewrite an untouched legacy value on blur', async () => {
    // This value reserializes differently ('  \n' hard break), so a save would rewrite it.
    const wrapper = await mountComponent({ value: 'Line one\nLine two' })
    const editor = wrapper.findComponent(RichTextEditor)

    editor.vm.$emit('focus')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('renders read-only when the field is not editable', async () => {
    const wrapper = await mountComponent({ readOnly: true })

    expect(wrapper.find('.tiptap').attributes('contenteditable')).toBe('false')
  })
})
