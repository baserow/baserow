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

  // Each drop captures an absolute ProseMirror position, then uploads
  // asynchronously. When an earlier drop's upload finishes it inserts an image
  // and shifts the document, so a position captured by a later drop is stale.
  // `trackPosition` maps it through the intervening transactions.
  test('inserts a concurrently dropped image at the position it was dropped at', async () => {
    const deferred = []
    const uploadFile = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          deferred.push(resolve)
        })
    )
    const wrapper = await mountEditor('AAA BBB', { uploadFile })
    const { view } = wrapper.vm.editor
    const docEnd = view.state.doc.content.size - 1

    // Drop one image at the very start, a second at the end, before either
    // upload resolves.
    view.posAtCoords = () => ({ pos: 1, inside: -1 })
    wrapper.find('.tiptap').trigger('drop', {
      clientX: 0,
      clientY: 0,
      dataTransfer: {
        files: [new File(['1'], 'first.png', { type: 'image/png' })],
        types: ['Files'],
        getData: () => '',
      },
    })
    view.posAtCoords = () => ({ pos: docEnd, inside: -1 })
    wrapper.find('.tiptap').trigger('drop', {
      clientX: 0,
      clientY: 0,
      dataTransfer: {
        files: [new File(['2'], 'second.png', { type: 'image/png' })],
        types: ['Files'],
        getData: () => '',
      },
    })
    await settleUploads()
    expect(deferred).toHaveLength(2)

    // The first drop resolves first and shifts the document.
    deferred[0]({
      data: {
        name: 'aaa_111.png',
        original_name: 'first.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/aaa_111.png',
      },
    })
    await settleUploads()
    deferred[1]({
      data: {
        name: 'bbb_222.png',
        original_name: 'second.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/bbb_222.png',
      },
    })
    await settleUploads()

    // The second image belongs after the text it was dropped past, not next to
    // the first image at the start.
    const markdown = wrapper.vm.serializeToMarkdown()
    expect(markdown.indexOf('[aaa_111.png]')).toBeLessThan(
      markdown.indexOf('BBB')
    )
    expect(markdown.indexOf('BBB')).toBeLessThan(
      markdown.indexOf('[bbb_222.png]')
    )
  })

  // Files of one drop upload one by one. The user may click elsewhere while a
  // later file is still uploading; it still belongs right after the previous
  // image of that drop, not at the moved cursor.
  test('keeps every image of one drop at the drop position', async () => {
    const deferred = []
    const uploadFile = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          deferred.push(resolve)
        })
    )
    const wrapper = await mountEditor('AAA BBB', { uploadFile })
    const { view } = wrapper.vm.editor
    const docEnd = view.state.doc.content.size - 1

    view.posAtCoords = () => ({ pos: docEnd, inside: -1 })
    wrapper.find('.tiptap').trigger('drop', {
      clientX: 0,
      clientY: 0,
      dataTransfer: {
        files: [
          new File(['1'], 'first.png', { type: 'image/png' }),
          new File(['2'], 'second.png', { type: 'image/png' }),
        ],
        types: ['Files'],
        getData: () => '',
      },
    })
    await settleUploads()
    expect(deferred).toHaveLength(1)
    deferred[0]({
      data: {
        name: 'aaa_111.png',
        original_name: 'first.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/aaa_111.png',
      },
    })
    await settleUploads()
    expect(deferred).toHaveLength(2)

    // The user clicks at the very start while the second file uploads.
    wrapper.vm.editor.commands.setTextSelection(1)
    deferred[1]({
      data: {
        name: 'bbb_222.png',
        original_name: 'second.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/bbb_222.png',
      },
    })
    await settleUploads()

    const markdown = wrapper.vm.serializeToMarkdown()
    expect(markdown.indexOf('BBB')).toBeLessThan(
      markdown.indexOf('[aaa_111.png]')
    )
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

  // Rich text images are Baserow user files only: a plain markdown image is
  // never rendered, so a public view cannot be made to fetch a third-party URL.
  test('renders a plain https markdown image as a link, not an img', async () => {
    const wrapper = await mountEditor(
      'see ![photo](https://example.com/photo.png) here',
      { uploadFile: vi.fn() }
    )

    expect(wrapper.find('.tiptap img').exists()).toBe(false)
    expect(wrapper.find('.tiptap').text()).toContain('photo')
    expect(wrapper.vm.serializeToMarkdown()).not.toContain('![photo]')
  })

  test('uploads an image copied from a browser, which also carries text/html', async () => {
    // "Copy image" puts the file on the clipboard next to `<img src=...>` HTML
    // and no plain text. The HTML would be dropped (external images are not
    // supported), so the file is the only thing the user can mean.
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'abc123_def456.png',
        original_name: 'shot.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/abc123_def456.png',
      },
    })
    const wrapper = await mountEditor('', { uploadFile })
    const file = new File(['png'], 'shot.png', { type: 'image/png' })

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
      'https://example.com/user_files/abc123_def456.png'
    )
  })

  test('pastes text, not the image file, when real text is on the clipboard', async () => {
    const uploadFile = vi.fn()
    const wrapper = await mountEditor('', { uploadFile })
    const file = new File(['png'], 'shot.png', { type: 'image/png' })

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

  test('uploads a dropped image whose extension the browser did not recognise', async () => {
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'abc123_def456.jpg',
        original_name: 'photo.jpg',
        original_extension: 'jpg',
        is_image: true,
        url: 'https://example.com/user_files/abc123_def456.jpg',
      },
    })
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
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'abc123_def456.png',
        original_name: 'shot.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/abc123_def456.png',
      },
    })
    const wrapper = await mountEditor('', { uploadFile })

    await pasteFile(wrapper, new File(['png'], 'shot.png)', { type: '' }))

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(uploadFile.mock.calls[0][0].name).toBe('shot.png')
  })

  test('uploads a dropped file without an extension', async () => {
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'abc123_def456.',
        original_name: 'photo',
        original_extension: '',
        is_image: true,
        url: 'https://example.com/user_files/abc123_def456.',
      },
    })
    const wrapper = await mountEditor('', { uploadFile })

    await dropFiles(wrapper, [new File(['jpg'], 'photo', { type: '' })])
    await settleUploads()

    expect(uploadFile).toHaveBeenCalledOnce()
    expect(wrapper.find('.tiptap img').exists()).toBe(true)
    expect(wrapper.vm.serializeToMarkdown()).toContain(
      '![photo][abc123_def456.]'
    )
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

  // The upload is asynchronous. The image belongs where it was pasted, not
  // wherever the selection is when the upload finishes: otherwise selecting
  // text meanwhile would get it replaced by the image.
  test('inserts a pasted image at the paste position', async () => {
    let resolveUpload
    const uploadFile = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve
        })
    )
    const wrapper = await mountEditor('AAA BBB', { uploadFile })
    const { editor } = wrapper.vm
    editor.commands.setTextSelection(editor.state.doc.content.size - 1)

    await pasteFile(wrapper, new File(['1'], 'shot.png', { type: 'image/png' }))
    // Select `AAA` while the upload is pending.
    editor.commands.setTextSelection({ from: 1, to: 4 })
    resolveUpload({
      data: {
        name: 'aaa_111.png',
        original_name: 'shot.png',
        original_extension: 'png',
        is_image: true,
        url: 'https://example.com/user_files/aaa_111.png',
      },
    })
    await settleUploads()

    const markdown = wrapper.vm.serializeToMarkdown()
    expect(markdown).toContain('AAA BBB')
    expect(markdown.indexOf('BBB')).toBeLessThan(
      markdown.indexOf('[aaa_111.png]')
    )
  })

  test('drops characters the reference cannot carry from the extension', async () => {
    const uploadFile = vi.fn().mockResolvedValue({
      data: {
        name: 'aaa_111.jpg',
        original_name: 'a.jpg',
        original_extension: 'jpg',
        is_image: true,
        url: 'https://example.com/user_files/aaa_111.jpg',
      },
    })
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
    expect(wrapper.vm.serializeToMarkdown()).toContain('![x][abc_def.png]')
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
