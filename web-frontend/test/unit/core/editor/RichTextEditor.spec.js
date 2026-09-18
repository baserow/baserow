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

  test('parses Markdown when the model value changes in read-only mode', async () => {
    const wrapper = await mountEditor('plain', { editable: false })

    await wrapper.setProps({ modelValue: '**bold**\nnext' })

    expect(wrapper.find('.tiptap strong').text()).toBe('bold')
    expect(wrapper.find('.tiptap br').exists()).toBe(true)
    expect(wrapper.vm.serializeToMarkdown()).toBe('**bold**  \nnext')
  })

  test('ignores external model value changes when editable', async () => {
    const wrapper = await mountEditor('original')

    await wrapper.setProps({ modelValue: '**changed**' })

    expect(wrapper.find('.tiptap strong').exists()).toBe(false)
    expect(wrapper.vm.serializeToMarkdown()).toBe('original')
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

  test('preserves trailing empty paragraphs copied from another rich text editor', async () => {
    const markdown = 'Line1\n\n\n\nLine3\n\n\n\nline5\n\n&nbsp;'
    const source = await mountEditor(markdown)
    const clipboard = {}
    const clipboardData = {
      clearData: () => {
        Object.keys(clipboard).forEach((type) => delete clipboard[type])
      },
      getData: (type) => clipboard[type] ?? '',
      setData: (type, value) => {
        clipboard[type] = value
      },
    }
    const copyEvent = new Event('copy', {
      bubbles: true,
      cancelable: true,
    })
    Object.defineProperty(copyEvent, 'clipboardData', {
      value: clipboardData,
    })

    source.vm.editor.commands.selectAll()
    source.find('.tiptap').element.dispatchEvent(copyEvent)
    expect(clipboard['text/plain']).toBe(markdown)

    const target = await mountEditor('')
    await target.find('.tiptap').trigger('paste', {
      // Some browsers only expose text/plain here. The editor-copy marker must
      // still prevent this Markdown from being inserted as literal plain text.
      clipboardData: {
        getData: (type) =>
          type === 'text/plain' ? clipboard['text/plain'] : '',
      },
    })

    expect(
      target.findAll('.tiptap p').map((paragraph) => paragraph.text())
    ).toStrictEqual(['Line1', '', 'Line3', '', 'line5', ''])
    expect(target.vm.serializeToMarkdown()).toBe(markdown)
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

  test('destroys editor resources when unmounted', async () => {
    const wrapper = await mountEditor('content')
    const destroyEditor = vi.spyOn(wrapper.vm.editor, 'destroy')
    const disconnectResizeObserver = vi.spyOn(
      wrapper.vm.resizeObserver,
      'disconnect'
    )

    wrapper.unmount()

    expect(destroyEditor).toHaveBeenCalledOnce()
    expect(disconnectResizeObserver).toHaveBeenCalledOnce()
  })

  test('keeps one root mousedown handler after recreating the editor', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: 'content',
        enableRichTextFormatting: true,
      },
    })

    await wrapper.setProps({ editable: false })
    await wrapper.setProps({ editable: true })

    const collapse = vi.spyOn(wrapper.vm.$refs.floatingMenu, 'collapse')
    wrapper.vm.$refs.root.dispatchEvent(
      new MouseEvent('mousedown', { bubbles: true })
    )

    expect(collapse).toHaveBeenCalledOnce()
  })
})

describe('RichTextEditor images', () => {
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
        enableImages: true,
        ...props,
      },
      global: {
        stubs: {
          RichTextEditorBubbleMenu: true,
          RichTextEditorFloatingMenu: true,
        },
      },
    })

  const settleUploads = async () => {
    // Uploads are awaited one by one, so let the promise chain settle.
    for (let i = 0; i < 10; i += 1) {
      await new Promise((resolve) => setTimeout(resolve))
    }
  }

  const pasteFile = async (wrapper, file) => {
    await wrapper.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: () => '',
        types: ['Files'],
        items: [{ type: file.type, getAsFile: () => file }],
      },
    })
    await settleUploads()
  }

  const dropFiles = async (wrapper, files) => {
    // jsdom has no layout, so ProseMirror can't map coordinates to a position
    // (and bails before handleDrop). Resolve every drop to the document end.
    const { view } = wrapper.vm.editor
    view.posAtCoords = () => ({
      pos: view.state.doc.content.size - 1,
      inside: -1,
    })
    await wrapper.find('.tiptap').trigger('drop', {
      clientX: 0,
      clientY: 0,
      dataTransfer: { files, types: ['Files'], getData: () => '' },
    })
    await settleUploads()
  }

  test('renders image markdown as text unless enableImages is set', async () => {
    const wrapper = await mountEditor(
      'see ![photo](https://example.com/photo.png) here',
      { enableImages: false }
    )

    expect(wrapper.find('.tiptap img').exists()).toBe(false)
    expect(wrapper.text()).toContain('photo')
  })

  test('inserts dropped images in drop order, one after the other', async () => {
    const uploadFile = vi
      .fn()
      .mockResolvedValueOnce({
        data: {
          name: 'aaa_111.png',
          original_name: 'first.png',
          original_extension: 'png',
          is_image: true,
          url: 'https://example.com/user_files/aaa_111.png',
        },
      })
      .mockResolvedValueOnce({
        data: {
          name: 'bbb_222.png',
          original_name: 'second.png',
          original_extension: 'png',
          is_image: true,
          url: 'https://example.com/user_files/bbb_222.png',
        },
      })
    const wrapper = await mountEditor('intro', { uploadFile })

    await dropFiles(wrapper, [
      new File(['1'], 'first.png', { type: 'image/png' }),
      new File(['2'], 'second.png', { type: 'image/png' }),
    ])

    expect(uploadFile).toHaveBeenCalledTimes(2)
    const sources = wrapper
      .findAll('.tiptap img')
      .map((image) => image.attributes('src'))
    expect(sources).toEqual([
      'https://example.com/user_files/aaa_111.png',
      'https://example.com/user_files/bbb_222.png',
    ])
    const markdown = wrapper.vm.serializeToMarkdown()
    expect(markdown.indexOf('[aaa_111.png]')).toBeLessThan(
      markdown.indexOf('[bbb_222.png]')
    )
  })

  test('renders a Baserow image ref from the stored value', async () => {
    const wrapper = await mountEditor(
      'text ![photo][abc123_def456.png](https://example.com/user_files/abc123_def456.png)',
      { uploadFile: vi.fn() }
    )

    const image = wrapper.find('.tiptap img')
    expect(image.exists()).toBe(true)
    expect(image.attributes('src')).toBe(
      'https://example.com/user_files/abc123_def456.png'
    )
    expect(wrapper.vm.serializeToMarkdown()).toContain(
      '![photo][abc123_def456.png](https://example.com/user_files/abc123_def456.png)'
    )
  })

  test('renders a plain https markdown image as an img', async () => {
    const wrapper = await mountEditor(
      'see ![photo](https://example.com/photo.png) here',
      { uploadFile: vi.fn() }
    )

    const image = wrapper.find('.tiptap img')
    expect(image.exists()).toBe(true)
    expect(image.attributes('src')).toBe('https://example.com/photo.png')
    expect(wrapper.vm.serializeToMarkdown()).toContain(
      '![photo](https://example.com/photo.png)'
    )
  })

  test('embeds an uploaded svg even though the backend does not flag it as image', async () => {
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'abc123_def456.svg',
        original_name: 'logo.svg',
        original_extension: 'svg',
        is_image: false,
        url: 'https://example.com/user_files/abc123_def456.svg',
      },
    })
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const wrapper = await mountEditor('', { uploadFile })

    await pasteFile(
      wrapper,
      new File(['<svg></svg>'], 'logo.svg', { type: 'image/svg+xml' })
    )

    expect(uploadFile).toHaveBeenCalledOnce()
    const image = wrapper.find('.tiptap img')
    expect(image.exists()).toBe(true)
    expect(image.attributes('src')).toBe(
      'https://example.com/user_files/abc123_def456.svg'
    )
    expect(image.attributes('alt')).toBe('logo')
    expect(dispatch).not.toHaveBeenCalledWith('toast/error', expect.anything())
    expect(wrapper.vm.serializeToMarkdown()).toContain(
      '![logo][abc123_def456.svg](https://example.com/user_files/abc123_def456.svg)'
    )
  })

  test('shows an error toast instead of embedding a non-image upload', async () => {
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'abc123_def456.pdf',
        original_name: 'doc.pdf',
        original_extension: 'pdf',
        is_image: false,
        url: 'https://example.com/user_files/abc123_def456.pdf',
      },
    })
    const dispatch = vi.spyOn(testApp.store, 'dispatch')
    const wrapper = await mountEditor('', { uploadFile })

    // Browsers can report a misleading mime type, so the server response is
    // what decides whether the file is embeddable.
    await pasteFile(
      wrapper,
      new File(['%PDF'], 'doc.pdf', { type: 'image/x-not-really' })
    )

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.find('.tiptap img').exists()).toBe(false)
    expect(dispatch).toHaveBeenCalledWith('toast/error', {
      title: 'richTextEditor.errorUnsupportedImageTitle',
      message: 'richTextEditor.errorUnsupportedImageMessage',
    })
    expect(wrapper.vm.serializeToMarkdown()).toBe('')
  })

  test('stops uploading the rest of the batch when the editor is torn down', async () => {
    // Control resolution by hand so the teardown lands mid-batch without
    // depending on any timing.
    const pending = []
    const uploadFile = vi.fn(
      () => new Promise((resolve) => pending.push(resolve))
    )
    const wrapper = await mountEditor('', { uploadFile })

    const uploading = wrapper.vm.uploadFiles([
      new File(['1'], 'first.png', { type: 'image/png' }),
      new File(['2'], 'second.png', { type: 'image/png' }),
    ])
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.vm.loadings).toHaveLength(2)

    wrapper.vm.teardownEditor()
    pending[0]({
      data: {
        name: 'aaa_111.png',
        original_name: 'first.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/aaa_111.png',
      },
    })
    await uploading

    // The first upload resolved after teardown, so it must not be inserted, and
    // the second must never be requested at all.
    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.vm.loadings).toHaveLength(0)
  })

  test('keeps inserting the batch when one upload fails', async () => {
    const imageResponse = (name, originalName) => ({
      data: {
        name,
        original_name: originalName,
        original_extension: 'png',
        is_image: true,
        url: `https://example.com/user_files/${name}`,
      },
    })
    // A real API failure carries an error handler; `notifyIf` rethrows anything
    // without one, so a bare Error would escape the upload loop.
    const notifyIf = vi.fn()
    const uploadFile = vi
      .fn()
      .mockResolvedValueOnce(imageResponse('aaa_111.png', 'first.png'))
      .mockRejectedValueOnce({ handler: { notifyIf } })
      .mockResolvedValueOnce(imageResponse('ccc_333.png', 'third.png'))
    const wrapper = await mountEditor('', { uploadFile })

    // Await the upload loop itself rather than a fixed number of ticks: the
    // rejection adds microtasks, so a tick count would be timing dependent.
    await wrapper.vm.uploadFiles([
      new File(['1'], 'first.png', { type: 'image/png' }),
      new File(['2'], 'second.png', { type: 'image/png' }),
      new File(['3'], 'third.png', { type: 'image/png' }),
    ])
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledTimes(3)
    const sources = wrapper
      .findAll('.tiptap img')
      .map((image) => image.attributes('src'))
    expect(sources).toEqual([
      'https://example.com/user_files/aaa_111.png',
      'https://example.com/user_files/ccc_333.png',
    ])
    // The user is told about the failure, and the loading indicator is cleared
    // for every file, including the one that failed.
    expect(notifyIf).toHaveBeenCalledOnce()
    expect(wrapper.vm.loadings).toHaveLength(0)
  })

  test('pastes as text instead of uploading when the clipboard also has text', async () => {
    const uploadFile = vi.fn()
    const wrapper = await mountEditor('', { uploadFile })
    const file = new File(['1'], 'shot.png', { type: 'image/png' })

    await wrapper.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: () => 'some copied text',
        types: ['text/plain', 'Files'],
        items: [{ type: file.type, getAsFile: () => file }],
      },
    })
    await settleUploads()

    expect(uploadFile).not.toHaveBeenCalled()
    expect(wrapper.find('.tiptap img').exists()).toBe(false)
  })

  test('uploads an image pasted from the clipboard', async () => {
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'aaa_111.png',
        original_name: 'shot.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/aaa_111.png',
      },
    })
    const wrapper = await mountEditor('', { uploadFile })

    await pasteFile(wrapper, new File(['1'], 'shot.png', { type: 'image/png' }))

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.find('.tiptap img').attributes('src')).toBe(
      'https://example.com/user_files/aaa_111.png'
    )
    expect(wrapper.vm.serializeToMarkdown()).toContain('[aaa_111.png]')
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
