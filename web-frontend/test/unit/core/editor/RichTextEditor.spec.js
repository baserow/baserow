import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor.vue'
import { plainTextToMarkdown } from '@baserow/modules/core/editor/richTextClipboard'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('RichTextEditor Markdown persistence', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountEditor = (modelValue, props = {}) =>
    testApp.mount(RichTextEditor, {
      props: {
        modelValue,
        enableRichTextFormatting: true,
        ...props,
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

  test('emits the document as ProseMirror JSON on update', async () => {
    const wrapper = await mountEditor('first')

    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()
    expect(emitted.at(-1)[0]).toMatchObject({ type: 'doc' })
  })

  test('preserves repeated blank lines pasted from a quoted grid cell', async () => {
    const wrapper = await mountEditor('')

    await wrapper.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: (type) => (type === 'text/plain' ? '"ciao\n\n\n\nmiao"' : ''),
      },
    })

    expect(
      wrapper.findAll('.tiptap p').map((paragraph) => paragraph.text())
    ).toStrictEqual(['ciao', '', '', '', 'miao'])
    expect(
      wrapper
        .findAll('.tiptap p')
        .slice(1, 4)
        .every((paragraph) => paragraph.find('br').exists())
    ).toBe(true)
    const reopened = await mountEditor(wrapper.vm.serializeToMarkdown())

    expect(reopened.find('.tiptap').html()).toBe(wrapper.find('.tiptap').html())
  })

  test('preserves repeated blank lines pasted as plain text', async () => {
    const wrapper = await mountEditor('')

    await wrapper.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: (type) => (type === 'text/plain' ? 'ciao\n\n\n\nmiao' : ''),
      },
    })

    const paragraphs = wrapper.findAll('.tiptap p')
    expect(paragraphs.map((paragraph) => paragraph.text())).toStrictEqual([
      'ciao',
      '',
      '',
      '',
      'miao',
    ])
    expect(
      paragraphs.slice(1, 4).every((paragraph) => paragraph.find('br').exists())
    ).toBe(true)
    const reopened = await mountEditor(wrapper.vm.serializeToMarkdown())

    expect(reopened.find('.tiptap').html()).toBe(wrapper.find('.tiptap').html())
  })

  test('renders repeated plain text newlines converted to Markdown', async () => {
    const markdown = plainTextToMarkdown('ciao\n\n\n\nmiao')
    const wrapper = await mountEditor(markdown)

    expect(
      wrapper.findAll('.tiptap p').map((paragraph) => paragraph.text())
    ).toStrictEqual(['ciao', '', '', '', 'miao'])
    const reopened = await mountEditor(wrapper.vm.serializeToMarkdown())

    expect(reopened.find('.tiptap').html()).toBe(wrapper.find('.tiptap').html())
  })

  test('keeps the selection menu hidden after its selection scrolls away', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: 'selected text',
        enableRichTextFormatting: true,
      },
    })
    await new Promise((resolve) => setTimeout(resolve))

    wrapper.vm.$refs.root.getBoundingClientRect = () => ({
      top: 100,
      bottom: 200,
    })
    wrapper.vm.editor.view.coordsAtPos = () => ({
      top: 300,
      bottom: 320,
      left: 100,
      right: 100,
    })
    wrapper.vm.editor.commands.focus()
    wrapper.vm.editor.commands.setTextSelection({ from: 1, to: 9 })
    await new Promise((resolve) => setTimeout(resolve))

    // Force it visible so the assertion proves the scroll handler hid it, not an
    // earlier selection-time visibility update.
    wrapper.vm.$refs.bubbleMenu.$el.style.visibility = 'visible'
    wrapper.vm.$refs.root.dispatchEvent(new Event('scroll'))
    await new Promise((resolve) => setTimeout(resolve))

    expect(wrapper.vm.$refs.bubbleMenu.$el.style.visibility).toBe('hidden')
  })
})

describe('RichTextEditor plain text mode', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountEditor = (modelValue, props = {}) =>
    testApp.mount(RichTextEditor, {
      props: { modelValue, ...props },
      global: {
        stubs: {
          RichTextEditorBubbleMenu: true,
          RichTextEditorFloatingMenu: true,
        },
      },
    })

  test('does not interpret Markdown syntax', async () => {
    const wrapper = await mountEditor('**bold** and # heading')

    expect(wrapper.find('.tiptap strong').exists()).toBe(false)
    expect(wrapper.find('.tiptap h1').exists()).toBe(false)
    expect(wrapper.find('.tiptap p').text()).toBe('**bold** and # heading')
  })

  test('serializes to plain text with newline separators', async () => {
    const wrapper = await mountEditor('first')
    wrapper.vm.focus()
    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })

    expect(wrapper.vm.serializeToMarkdown()).toBe('first\n')
  })

  test('renders a stored comment document with mentions', async () => {
    const legacyDocument = {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'Hello ' },
            { type: 'mention', attrs: { id: '5' } },
            { type: 'text', text: ' and ' },
            { type: 'mention', attrs: { id: '99' } },
            { type: 'hardBreak' },
            { type: 'text', text: 'second line' },
          ],
        },
      ],
    }
    const wrapper = await mountEditor(legacyDocument, {
      editable: false,
      mentionableUsers: [{ user_id: 5, name: 'Jane Doe' }],
    })

    const mentions = wrapper.findAll('.rich-text-editor__mention')
    expect(mentions).toHaveLength(2)
    expect(mentions[0].text()).toBe('@Jane Doe')
    expect(mentions[1].text()).toBe('@99')
    expect(mentions[1].classes()).toContain(
      'rich-text-editor__mention--user-gone'
    )
    expect(wrapper.find('.tiptap').attributes('contenteditable')).toBe('false')
    expect(wrapper.find('.tiptap br').exists()).toBe(true)
  })
})

describe('RichTextEditor enter stops editing', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountEditor = (modelValue) =>
    testApp.mount(RichTextEditor, {
      props: { modelValue, enterStopEdit: true },
      global: {
        stubs: {
          RichTextEditorBubbleMenu: true,
          RichTextEditorFloatingMenu: true,
        },
      },
    })

  test('emits stop-edit instead of inserting a paragraph', async () => {
    const wrapper = await mountEditor('some comment')

    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('stop-edit')).toHaveLength(1)
    expect(wrapper.findAll('.tiptap p')).toHaveLength(1)
  })

  test('does not emit stop-edit while the document is empty', async () => {
    const wrapper = await mountEditor(null)

    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('stop-edit')).toBeUndefined()
  })
})
