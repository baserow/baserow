import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('RichTextEditor Markdown persistence', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountEditor = (modelValue) =>
    testApp.mount(RichTextEditor, {
      props: {
        modelValue,
        enableRichTextFormatting: true,
      },
      global: {
        stubs: {
          RichTextEditorBubbleMenu: true,
          RichTextEditorFloatingMenu: true,
        },
      },
    })

  test('renders and saves empty lines from Markdown', async () => {
    const wrapper = await mountEditor('A\n\n\n\nB')
    const paragraphs = wrapper.findAll('.tiptap p')

    expect(paragraphs).toHaveLength(3)
    expect(paragraphs.map((paragraph) => paragraph.text())).toStrictEqual([
      'A',
      '',
      'B',
    ])
    expect(wrapper.vm.serializeToMarkdown()).toBe('A\n\n\n\nB')
  })

  test('treats a nullable database value as empty content', async () => {
    const wrapper = await mountEditor(null)

    expect(wrapper.findAll('.tiptap p')).toHaveLength(1)
    expect(wrapper.vm.serializeToMarkdown()).toBe('')
  })

  test('parses Markdown when the model value changes', async () => {
    const wrapper = await mountEditor('plain')

    await wrapper.setProps({ modelValue: '**bold**\nnext' })

    expect(wrapper.find('.tiptap strong').text()).toBe('bold')
    expect(wrapper.find('.tiptap br').exists()).toBe(true)
    expect(wrapper.vm.serializeToMarkdown()).toBe('**bold**  \nnext')
  })

  test('inserts a new paragraph when Enter is pressed', async () => {
    const wrapper = await mountEditor('first')
    const editor = wrapper.find('.tiptap')

    await editor.trigger('keydown', { key: 'Enter', code: 'Enter' })

    expect(wrapper.findAll('.tiptap p')).toHaveLength(2)
  })
})
