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

  test('applies external model value changes when editable', async () => {
    const wrapper = await mountEditor('original')

    await wrapper.setProps({ modelValue: '**changed**' })

    // An external change (a realtime update) has to reach the document:
    // keeping the old one lets a later save write it over the newer value.
    expect(wrapper.find('.tiptap strong').text()).toBe('changed')
    expect(wrapper.vm.serializeToMarkdown()).toBe('**changed**')
  })

  test('ignores the value it emitted itself when editable', async () => {
    const wrapper = await mountEditor('original')

    wrapper.vm.editor.commands.setContent('typed', { emitUpdate: true })
    await wrapper.vm.$nextTick()

    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted).toBeTruthy()

    // Echoing that value back must not reload the document, which would reset
    // the caret on every keystroke.
    await wrapper.setProps({ modelValue: emitted[emitted.length - 1][0] })

    expect(wrapper.vm.serializeToMarkdown()).toBe('typed')
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

  const userFileName = (letter, digit, extension = 'png') =>
    `${letter.repeat(32)}_${digit.repeat(64)}.${extension}`
  const FIRST = userFileName('A', '1')
  const SECOND = userFileName('B', '2')
  const THIRD = userFileName('C', '3')
  const userFileUrl = (name) => `https://example.com/media/user_files/${name}`
  const thumbnail = (size, name, width, height) => ({
    url: `https://example.com/media/thumbnails/${size}/${name}`,
    width,
    height,
  })

  const uploadResponse = (name, originalName, overrides = {}) => ({
    data: {
      size: 3,
      mime_type: 'image/png',
      is_image: true,
      image_width: 1,
      image_height: 1,
      uploaded_at: '2026-09-25T10:00:00Z',
      url: userFileUrl(name),
      thumbnails: {
        tiny: thumbnail('tiny', name, null, 21),
        small: thumbnail('small', name, 48, 48),
        card_cover: thumbnail('card_cover', name, 300, 160),
      },
      name,
      original_name: originalName,
      ...overrides,
    },
  })

  const imageMarkdown = (alt, name) =>
    `![${alt}][${name}](${userFileUrl(name)})`

  const deferredUploads = () => {
    const pending = []
    const uploadFile = vi.fn(
      () =>
        new Promise((resolve, reject) => {
          pending.push({ resolve, reject })
        })
    )
    return { uploadFile, pending }
  }

  const uploadPlaceholders = (wrapper) =>
    wrapper.findAll('.tiptap .rich-text-editor__image-uploading')

  const png = (name) => new File(['png'], name, { type: 'image/png' })

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

  const dropFiles = async (wrapper, files, pos = null) => {
    // happy-dom has no layout, so posAtCoords is stubbed to `pos` or the end of the text.
    const { view } = wrapper.vm.editor
    view.posAtCoords = () => ({
      pos: pos ?? view.state.doc.content.size - 1,
      inside: -1,
    })
    await wrapper.find('.tiptap').trigger('drop', {
      clientX: 0,
      clientY: 0,
      dataTransfer: { files, types: ['Files'], getData: () => '' },
    })
    await settleUploads()
  }

  test('focus after a trailing image does not select it', async () => {
    const wrapper = await mountEditor(
      '![photo][abc_def.png](https://example.com/abc_def.png)'
    )

    wrapper.vm.focus()
    wrapper.vm.editor.commands.insertContent('tail')

    expect(wrapper.vm.serializeToMarkdown()).toContain('![photo][abc_def.png]')
    expect(wrapper.vm.serializeToMarkdown()).toContain('tail')
  })

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
      .mockResolvedValueOnce(uploadResponse(FIRST, 'first.png'))
      .mockResolvedValueOnce(uploadResponse(SECOND, 'second.png'))
    const wrapper = await mountEditor('intro', { uploadFile })

    await dropFiles(wrapper, [png('first.png'), png('second.png')])

    expect(uploadFile).toHaveBeenCalledTimes(2)
    const sources = wrapper
      .findAll('.tiptap img')
      .map((image) => image.attributes('src'))
    expect(sources).toEqual([userFileUrl(FIRST), userFileUrl(SECOND)])
    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `intro${imageMarkdown('first', FIRST)}${imageMarkdown('second', SECOND)}`
    )
  })

  test('shows a placeholder for every file of a drop, in file order, until each upload finishes', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('intro', { uploadFile })

    await dropFiles(wrapper, [png('first.png'), png('second.png')])

    expect(uploadPlaceholders(wrapper)).toHaveLength(2)
    expect(wrapper.find('.tiptap img').exists()).toBe(false)

    pending[0].resolve(uploadResponse(FIRST, 'first.png'))
    await settleUploads()

    expect(uploadPlaceholders(wrapper)).toHaveLength(1)

    pending[1].resolve(uploadResponse(SECOND, 'second.png'))
    await settleUploads()

    expect(uploadPlaceholders(wrapper)).toHaveLength(0)
    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `intro${imageMarkdown('first', FIRST)}${imageMarkdown('second', SECOND)}`
    )
  })

  test('keeps drop order when a later drop finishes uploading first', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('intro', { uploadFile })

    await dropFiles(wrapper, [png('first.png')])
    await dropFiles(wrapper, [png('second.png')])
    expect(pending).toHaveLength(2)

    pending[1].resolve(uploadResponse(SECOND, 'second.png'))
    await settleUploads()
    pending[0].resolve(uploadResponse(FIRST, 'first.png'))
    await settleUploads()

    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `intro${imageMarkdown('first', FIRST)}${imageMarkdown('second', SECOND)}`
    )
  })

  test('keeps text typed during an upload after the image, and the caret where it was', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('intro', { uploadFile })
    const { editor } = wrapper.vm
    editor.commands.setTextSelection(editor.state.doc.content.size - 1)

    await dropFiles(wrapper, [png('shot.png')])
    editor.commands.insertContent(' more')
    const caret = editor.state.selection.from

    pending[0].resolve(uploadResponse(FIRST, 'shot.png'))
    await settleUploads()

    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `intro${imageMarkdown('shot', FIRST)} more`
    )
    expect(editor.state.selection.empty).toBe(true)
    expect(editor.state.selection.from).toBe(caret)
  })

  test('inserts a concurrently dropped image at the position it was dropped at', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('AAA BBB', { uploadFile })

    await dropFiles(wrapper, [png('first.png')], 1)
    await dropFiles(wrapper, [png('second.png')])
    expect(pending).toHaveLength(2)

    pending[0].resolve(uploadResponse(FIRST, 'first.png'))
    await settleUploads()
    pending[1].resolve(uploadResponse(SECOND, 'second.png'))
    await settleUploads()

    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `${imageMarkdown('first', FIRST)}AAA BBB${imageMarkdown('second', SECOND)}`
    )
  })

  test('keeps every image of one drop at the drop position when the caret moves', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('AAA BBB', { uploadFile })

    await dropFiles(wrapper, [png('first.png'), png('second.png')])
    pending[0].resolve(uploadResponse(FIRST, 'first.png'))
    await settleUploads()
    expect(pending).toHaveLength(2)

    wrapper.vm.editor.commands.setTextSelection(1)
    pending[1].resolve(uploadResponse(SECOND, 'second.png'))
    await settleUploads()

    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `AAA BBB${imageMarkdown('first', FIRST)}${imageMarkdown('second', SECOND)}`
    )
  })

  test('removes the placeholder of a failed upload', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('intro', { uploadFile })
    await dropFiles(wrapper, [png('shot.png')])
    expect(uploadPlaceholders(wrapper)).toHaveLength(1)

    // A real API failure carries an error handler; `notifyIf` rethrows anything without one.
    const notifyIf = vi.fn()
    pending[0].reject({ handler: { notifyIf } })
    await settleUploads()

    expect(notifyIf).toHaveBeenCalledOnce()
    expect(uploadPlaceholders(wrapper)).toHaveLength(0)
    expect(wrapper.vm.serializeToMarkdown()).toBe('intro')
  })

  test('emits upload-settled for each settled upload, once its image is in the document', async () => {
    const { uploadFile, pending } = deferredUploads()
    const settled = []
    const wrapper = await mountEditor('intro', {
      uploadFile,
      onUploadSettled: () => settled.push(wrapper.vm.serializeToMarkdown()),
    })

    await dropFiles(wrapper, [png('first.png'), png('second.png')])
    expect(settled).toEqual([])

    pending[0].resolve(uploadResponse(FIRST, 'first.png'))
    await settleUploads()
    pending[1].reject({ handler: { notifyIf: vi.fn() } })
    await settleUploads()

    const withFirst = `intro${imageMarkdown('first', FIRST)}`
    expect(settled).toEqual([withFirst, withFirst])
  })

  test('saves and emits nothing of an upload that is still in progress', async () => {
    const { uploadFile } = deferredUploads()
    const wrapper = await mountEditor('intro', { uploadFile })

    await dropFiles(wrapper, [png('shot.png')])

    expect(uploadPlaceholders(wrapper)).toHaveLength(1)
    expect(wrapper.vm.serializeToMarkdown()).toBe('intro')
    expect(wrapper.vm.isDirty()).toBe(false)
    const emitted = wrapper.emitted('update:modelValue') ?? []
    expect(JSON.stringify(emitted)).not.toContain('"uploadId":"')
  })

  test('leaves no placeholder behind when the editor is recreated mid-upload', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('intro', {
      uploadFile,
      'onUpdate:modelValue': (value) => wrapper.setProps({ modelValue: value }),
    })
    await dropFiles(wrapper, [png('shot.png')])
    expect(uploadPlaceholders(wrapper)).toHaveLength(1)

    await wrapper.setProps({ editable: false })
    pending[0].resolve(uploadResponse(FIRST, 'shot.png'))
    await settleUploads()

    expect(uploadPlaceholders(wrapper)).toHaveLength(0)
    expect(wrapper.find('.tiptap img').exists()).toBe(false)
    expect(wrapper.vm.serializeToMarkdown()).toBe('intro')
  })

  test('keeps an upload placeholder when the value is replaced from outside', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('intro', { uploadFile })
    await dropFiles(wrapper, [png('shot.png')])

    await wrapper.setProps({ modelValue: 'intro and more' })

    expect(uploadPlaceholders(wrapper)).toHaveLength(1)

    pending[0].resolve(uploadResponse(FIRST, 'shot.png'))
    await settleUploads()

    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `intro${imageMarkdown('shot', FIRST)} and more`
    )
  })

  test('keeps an image pasted into a blank line on that line when its own save comes back mid-upload', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('intro\n\n\n\noutro', { uploadFile })
    const { editor } = wrapper.vm
    editor.commands.setTextSelection(8)

    await pasteFile(wrapper, png('shot.png'))

    expect(wrapper.vm.isDirty()).toBe(false)
    expect(wrapper.vm.serializeToMarkdown()).toBe('intro\n\n\n\noutro')

    editor.commands.insertContentAt(editor.state.doc.content.size - 1, '!')
    await wrapper.setProps({ modelValue: wrapper.vm.serializeToMarkdown() })
    pending[0].resolve(uploadResponse(FIRST, 'shot.png'))
    await settleUploads()

    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `intro\n\n${imageMarkdown('shot', FIRST)}\n\noutro!`
    )
  })

  test.each([
    ['dropped', (wrapper, file) => dropFiles(wrapper, [file], 5)],
    [
      'pasted',
      (wrapper, file) => {
        wrapper.vm.editor.commands.setTextSelection(5)
        return pasteFile(wrapper, file)
      },
    ],
  ])('puts an image %s inside a code block after the block', async (_, add) => {
    const { uploadFile, pending } = deferredUploads()
    const code = '```\nconst a = 1\n```'
    const wrapper = await mountEditor(code, { uploadFile })

    await add(wrapper, png('shot.png'))

    expect(wrapper.vm.serializeToMarkdown()).toBe(code)

    pending[0].resolve(uploadResponse(FIRST, 'shot.png'))
    await settleUploads()

    expect(wrapper.findAll('.tiptap pre')).toHaveLength(1)
    expect(wrapper.find('.tiptap pre').text()).toBe('const a = 1')
    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `${code}\n\n${imageMarkdown('shot', FIRST)}`
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

  test.each([
    [
      'an uploaded image',
      'see ![x][abc_def.png](https://example.com/abc_def.png) end',
    ],
    ['an external image', 'see ![x](https://example.com/photo.png) end'],
  ])('keeps text around %s in one paragraph', async (_, markdown) => {
    const wrapper = await mountEditor(markdown, { uploadFile: vi.fn() })

    expect(wrapper.findAll('.tiptap p')).toHaveLength(1)
    expect(wrapper.vm.serializeToMarkdown()).toBe(markdown)
  })

  test('keeps an external image as a placeholder and saves it unchanged', async () => {
    const markdown = '![photo](https://example.com/photo.png)'
    const wrapper = await mountEditor(markdown, { uploadFile: vi.fn() })

    expect(wrapper.find('.tiptap img').exists()).toBe(false)
    expect(
      wrapper.find('.tiptap .rich-text-editor__image-placeholder').exists()
    ).toBe(true)
    expect(wrapper.vm.serializeToMarkdown()).toBe(markdown)
  })

  test('uploads an image copied from a browser, which also carries text/html', async () => {
    // "Copy image" puts the file on the clipboard next to `<img src=...>` HTML
    // and no plain text. The HTML would be dropped (external images are not
    // supported), so the file is the only thing the user can mean.
    const uploadFile = vi
      .fn()
      .mockResolvedValue(uploadResponse(FIRST, 'shot.png'))
    const wrapper = await mountEditor('', { uploadFile })
    const file = png('shot.png')

    await wrapper.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: (type) =>
          type === 'text/html' ? '<img src="https://ext.example/a.png">' : '',
        types: ['text/html', 'Files'],
        items: [
          { type: 'text/html', getAsFile: () => null },
          { type: file.type, getAsFile: () => file },
        ],
      },
    })
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.find('.tiptap img').attributes('src')).toBe(
      userFileUrl(FIRST)
    )
  })

  test('pastes text, not the image file, when real text is on the clipboard', async () => {
    const uploadFile = vi.fn()
    const wrapper = await mountEditor('', { uploadFile })
    const file = png('shot.png')

    await wrapper.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: (type) => (type === 'text/plain' ? 'hello' : ''),
        types: ['text/plain', 'Files'],
        items: [{ type: file.type, getAsFile: () => file }],
      },
    })
    await settleUploads()

    expect(uploadFile).not.toHaveBeenCalled()
  })

  test('embeds an uploaded svg even though the backend does not flag it as image', async () => {
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        size: 11,
        mime_type: 'application/octet-stream',
        is_image: false,
        image_width: null,
        image_height: null,
        uploaded_at: '2026-09-25T10:00:00Z',
        url: 'https://example.com/user_files/abc123_def456.svg',
        thumbnails: null,
        name: 'abc123_def456.svg',
        original_name: 'logo.svg',
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

  test('uploads a dropped image whose extension the browser did not recognise', async () => {
    const uploadFile = vi.fn().mockResolvedValue(
      uploadResponse(userFileName('A', '1', 'jpg'), 'photo.jpg', {
        mime_type: 'image/jpeg',
      })
    )
    const wrapper = await mountEditor('', { uploadFile })

    // A real browser gives `photo.jpg)` an empty type.
    await dropFiles(wrapper, [new File(['jpg'], 'photo.jpg)', { type: '' })])
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledOnce()
    const uploaded = uploadFile.mock.calls[0][0]
    expect(uploaded.name).toBe('photo.jpg')
    expect(uploaded.type).toBe('image/jpeg')
    expect(wrapper.find('.tiptap img').exists()).toBe(true)
  })

  test('uploads a pasted image file with an empty type', async () => {
    const uploadFile = vi
      .fn()
      .mockResolvedValue(uploadResponse(FIRST, 'shot.png'))
    const wrapper = await mountEditor('', { uploadFile })

    await pasteFile(wrapper, new File(['png'], 'shot.png)', { type: '' }))

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(uploadFile.mock.calls[0][0].name).toBe('shot.png')
  })

  test('uploads a dropped file without an extension', async () => {
    const name = userFileName('A', '1', '')
    const uploadFile = vi
      .fn()
      .mockResolvedValue(
        uploadResponse(name, 'photo', { mime_type: 'image/jpeg' })
      )
    const wrapper = await mountEditor('', { uploadFile })

    await dropFiles(wrapper, [new File(['jpg'], 'photo', { type: '' })])
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.find('.tiptap img').exists()).toBe(true)
    expect(wrapper.vm.serializeToMarkdown()).toContain(`![photo][${name}]`)
  })

  test('ignores a dropped file typed as a non-image', async () => {
    const uploadFile = vi.fn()
    const wrapper = await mountEditor('', { uploadFile })

    await dropFiles(wrapper, [
      new File(['x'], 'notes.txt', { type: 'text/plain' }),
    ])
    await settleUploads()

    expect(uploadFile).not.toHaveBeenCalled()
  })

  test('shows an error toast instead of embedding a non-image upload', async () => {
    const uploadFile = vi.fn().mockResolvedValue(
      uploadResponse(userFileName('A', '1', 'pdf'), 'doc.pdf', {
        mime_type: 'application/pdf',
        is_image: false,
        image_width: null,
        image_height: null,
        thumbnails: null,
      })
    )
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
    expect(uploadPlaceholders(wrapper)).toHaveLength(0)
    expect(dispatch).toHaveBeenCalledWith('toast/error', {
      title: 'richTextEditor.errorUnsupportedImageTitle',
      message: 'richTextEditor.errorUnsupportedImageMessage',
    })
    expect(wrapper.vm.serializeToMarkdown()).toBe('')
  })

  test('stops uploading the rest of the batch when the editor is torn down', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('', { uploadFile })

    const uploading = wrapper.vm.uploadFiles([
      png('first.png'),
      png('second.png'),
    ])
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledOnce()

    wrapper.vm.teardownEditor()
    pending[0].resolve(uploadResponse(FIRST, 'first.png'))
    await uploading

    // The first upload resolved after teardown, so it must not be inserted, and
    // the second must never be requested at all.
    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.emitted('upload-settled')).toBeUndefined()
  })

  test('keeps inserting the batch when one upload fails', async () => {
    // A real API failure carries an error handler; `notifyIf` rethrows anything
    // without one, so a bare Error would escape the upload loop.
    const notifyIf = vi.fn()
    const uploadFile = vi
      .fn()
      .mockResolvedValueOnce(uploadResponse(FIRST, 'first.png'))
      .mockRejectedValueOnce({ handler: { notifyIf } })
      .mockResolvedValueOnce(uploadResponse(THIRD, 'third.png'))
    const wrapper = await mountEditor('', { uploadFile })

    // Await the upload loop itself rather than a fixed number of ticks: the
    // rejection adds microtasks, so a tick count would be timing dependent.
    await wrapper.vm.uploadFiles([
      png('first.png'),
      png('second.png'),
      png('third.png'),
    ])
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledTimes(3)
    const sources = wrapper
      .findAll('.tiptap img')
      .map((image) => image.attributes('src'))
    expect(sources).toEqual([userFileUrl(FIRST), userFileUrl(THIRD)])
    expect(notifyIf).toHaveBeenCalledOnce()
    expect(uploadPlaceholders(wrapper)).toHaveLength(0)
  })

  test('pastes as text instead of uploading when the clipboard also has text', async () => {
    const uploadFile = vi.fn()
    const wrapper = await mountEditor('', { uploadFile })
    const file = png('shot.png')

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

  // Selecting text while the upload is pending must not get it replaced by the image.
  test('inserts a pasted image at the paste position', async () => {
    const { uploadFile, pending } = deferredUploads()
    const wrapper = await mountEditor('AAA BBB', { uploadFile })
    const { editor } = wrapper.vm
    editor.commands.setTextSelection(editor.state.doc.content.size - 1)

    await pasteFile(wrapper, png('shot.png'))
    editor.commands.setTextSelection({ from: 1, to: 4 })
    pending[0].resolve(uploadResponse(FIRST, 'shot.png'))
    await settleUploads()

    expect(wrapper.vm.serializeToMarkdown()).toBe(
      `AAA BBB${imageMarkdown('shot', FIRST)}`
    )
  })

  test('drops characters the reference cannot carry from the extension', async () => {
    const uploadFile = vi.fn().mockResolvedValue(
      uploadResponse(userFileName('A', '1', 'jpg'), 'a.jpg', {
        mime_type: 'image/jpeg',
      })
    )
    const wrapper = await mountEditor('', { uploadFile })

    await pasteFile(wrapper, new File(['1'], 'a.jpg)', { type: 'image/jpeg' }))

    expect(uploadFile).toHaveBeenCalledOnce()
    const uploaded = uploadFile.mock.calls[0][0]
    expect(uploaded.name).toBe('a.jpg')
    expect(uploaded.type).toBe('image/jpeg')
  })

  test('shows a placeholder for pasted HTML whose src Baserow did not hand out', async () => {
    const wrapper = await mountEditor('', { uploadFile: vi.fn() })

    wrapper.vm.editor.commands.insertContent(
      '<img src="https://evil.example.com/p.png" alt="x" data-user-file-name="abc_def.png">'
    )
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.tiptap img').exists()).toBe(false)
    expect(
      wrapper.find('.tiptap .rich-text-editor__image-placeholder').exists()
    ).toBe(true)
    // The saved value feeds the optimistic preview, which would load the URL.
    expect(wrapper.vm.serializeToMarkdown()).toBe('![x][abc_def.png]')
  })

  test('uploads an image pasted from the clipboard', async () => {
    const uploadFile = vi
      .fn()
      .mockResolvedValue(uploadResponse(FIRST, 'shot.png'))
    const wrapper = await mountEditor('', { uploadFile })

    await pasteFile(wrapper, png('shot.png'))

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.find('.tiptap img').attributes('src')).toBe(
      userFileUrl(FIRST)
    )
    expect(wrapper.vm.serializeToMarkdown()).toBe(imageMarkdown('shot', FIRST))
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
