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

  const userFileName = `${'a'.repeat(32)}_${'b'.repeat(64)}.png`

  const uploadedUserFile = {
    size: 3,
    mime_type: 'image/png',
    is_image: true,
    image_width: 1,
    image_height: 1,
    uploaded_at: '2026-09-25T10:00:00Z',
    url: `http://localhost:8000/media/user_files/${userFileName}`,
    thumbnails: {
      tiny: {
        url: `http://localhost:8000/media/thumbnails/tiny/${userFileName}`,
        width: null,
        height: 21,
      },
      small: {
        url: `http://localhost:8000/media/thumbnails/small/${userFileName}`,
        width: 48,
        height: 48,
      },
      card_cover: {
        url: `http://localhost:8000/media/thumbnails/card_cover/${userFileName}`,
        width: 300,
        height: 160,
      },
    },
    name: userFileName,
    original_name: 'screenshot.png',
  }

  const settleUploads = async () => {
    for (let i = 0; i < 10; i += 1) {
      await new Promise((resolve) => setTimeout(resolve))
    }
  }

  const pasteImage = async (wrapper) => {
    const file = new File(['png'], 'screenshot.png', { type: 'image/png' })
    await wrapper.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: () => '',
        types: ['Files'],
        items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      },
    })
    await settleUploads()
  }

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

  test('keeps the value without throwing when the editor ref is gone', async () => {
    const wrapper = await mountComponent()
    // The child editor unmounts before the modal-close blur reaches beforeSave.
    wrapper.vm.$refs.input = null

    expect(() => wrapper.vm.beforeSave()).not.toThrow()
    expect(wrapper.vm.beforeSave()).toBe('**bold** text')
  })

  test('uploads a pasted image and saves its reference on blur', async () => {
    testApp.mock.onPost('/user-files/upload-file/').reply(200, uploadedUserFile)
    const wrapper = await mountComponent()
    const editor = wrapper.findComponent(RichTextEditor)

    editor.vm.$emit('focus')
    await pasteImage(wrapper)
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    expect(testApp.mock.history.post.map((request) => request.url)).toEqual([
      '/user-files/upload-file/',
    ])
    const [[newValue]] = wrapper.emitted('update')
    expect(newValue).toContain(`![screenshot][${userFileName}]`)
  })

  test.each([{ readOnly: true }, { allowImageUpload: false }])(
    'does not upload a pasted image when %s',
    async (props) => {
      testApp.mock
        .onPost('/user-files/upload-file/')
        .reply(200, uploadedUserFile)
      const wrapper = await mountComponent(props)

      await pasteImage(wrapper)

      expect(testApp.mock.history.post).toHaveLength(0)
      expect(wrapper.find('.tiptap img').exists()).toBe(false)
    }
  )
})
