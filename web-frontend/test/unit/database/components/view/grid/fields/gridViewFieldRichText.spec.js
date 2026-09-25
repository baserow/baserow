import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRichText'
import FieldRichTextModal from '@baserow/modules/database/components/view/FieldRichTextModal'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'

// Stubbing the tiptap-backed editor keeps the test focused on the modal flow. Like
// the real editor, its serialized output reflects live content, not the lagging prop.
const RichTextEditorStub = {
  name: 'RichTextEditor',
  props: {
    modelValue: { type: [String, Object], default: '' },
    menuContainer: { type: [Object, Function], default: undefined },
    scrollableAreaElement: {
      type: [Object, Array, Function],
      default: null,
    },
  },
  emits: ['update:modelValue'],
  data() {
    return { content: this.modelValue || '' }
  },
  watch: {
    modelValue(value) {
      this.content = value || ''
    },
  },
  template: '<div class="rich-text-editor-stub"></div>',
  methods: {
    setContent(value) {
      this.content = value
      this.$emit('update:modelValue', value)
    },
    serializeToMarkdown() {
      return this.content || ''
    },
    focus() {},
    isDirty() {
      return true
    },
    isEventTargetInside() {
      return false
    },
  },
}

describe('GridViewFieldRichText component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    const app = testApp.getApp()
    app.$config.public = {
      ...app.$config.public,
      baserowMaxFieldTextLength: 10,
    }
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
    testApp.mount(GridViewFieldRichText, {
      props: {
        field,
        value: 'hello',
        selected: true,
        readOnly: false,
        storePrefix: 'page/',
        workspaceId: 10,
        ...props,
      },
      global: { stubs: { RichTextEditor: RichTextEditorStub } },
    })

  const editAndExpand = async (wrapper) => {
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()
    wrapper.vm.$refs.expandedModal.toggle()
    await wrapper.vm.$nextTick()
  }

  test('expanding into the modal opens it without breaking validation', async () => {
    const wrapper = await mountComponent()
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    // The modal editor only mounts on the next tick, so validation running during
    // this render must not assume it exists. Regression for the crash on open.
    wrapper.vm.$refs.expandedModal.toggle()
    expect(() => wrapper.vm.getError()).not.toThrow()

    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isModalOpen()).toBe(true)
    expect(
      wrapper
        .findComponent(FieldRichTextModal)
        .find('.rich-text-editor-stub')
        .exists()
    ).toBe(true)
  })

  test('closing the modal saves the value edited inside it', async () => {
    const wrapper = await mountComponent()
    await editAndExpand(wrapper)

    wrapper
      .findComponent(FieldRichTextModal)
      .findComponent(RichTextEditorStub)
      .vm.setContent('world')
    await wrapper.vm.$nextTick()

    wrapper.vm.$refs.expandedModal.hide()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')[0]).toEqual(['world', 'hello'])
  })

  test('shows the max-length error in the inline cell editor', async () => {
    const wrapper = await mountComponent()
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    wrapper.findComponent(RichTextEditorStub).vm.setContent('x'.repeat(15))
    await wrapper.vm.$nextTick()

    const error = wrapper.find('.grid-view__cell-error')
    expect(error.exists()).toBe(true)
    expect(error.isVisible()).toBe(true)
    expect(error.text()).toBe('fieldErrors.maxCharsExceeded')
  })

  test('does not save when editing ends without any edits', async () => {
    const wrapper = await mountComponent()
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    wrapper.vm.cancel()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('does not save when an external value arrives without any edits', async () => {
    const wrapper = await mountComponent()
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    // A realtime update while the cell is open is not a user edit, so leaving
    // the cell must not write the editor back over the value that arrived.
    await wrapper.setProps({ value: 'remote' })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.hasEdits).toBe(false)

    wrapper.vm.cancel()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('lets TipTap handle paste events while editing', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.vm.onPaste()).toBe(false)

    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.onPaste()).toBe(true)
  })

  test('parses a copied rich text grid cell when pasting while editing', async () => {
    const markdown = '# title\n\n\n\nciao\n\n\n\nmiao\n\n&nbsp;'
    const gridBody = document.createElement('div')
    gridBody.className = 'grid-view__body'
    document.body.appendChild(gridBody)

    const wrapper = await testApp.mount(GridViewFieldRichText, {
      attachTo: gridBody,
      props: {
        field,
        value: '',
        selected: true,
        readOnly: false,
        storePrefix: 'page/',
        workspaceId: 10,
      },
      global: {
        stubs: {
          FieldRichTextModal: {
            template: '<div></div>',
            methods: { isOpen: () => false },
          },
        },
      },
    })
    const copyData = wrapper.vm.prepareValuesForCopy(
      [field],
      [{ field_1: markdown }]
    )
    const { tsvData } = wrapper.vm.formatClipboardDataAndStoreRichCopy(copyData)

    expect(tsvData).toBe(`"${markdown}"`)

    wrapper.vm.edit()
    await new Promise((resolve) => setTimeout(resolve))

    const editor = wrapper.findComponent(RichTextEditor)
    await editor.find('.tiptap').trigger('paste', {
      clipboardData: {
        getData: (type) => (type === 'text/plain' ? tsvData : ''),
      },
    })

    expect(editor.find('h1').text()).toBe('title')
    expect(editor.findAll('.tiptap p').map((node) => node.text())).toEqual([
      'ciao',
      '',
      'miao',
      '',
    ])
    expect(editor.find('.tiptap').text()).not.toContain('&nbsp;')
    expect(editor.vm.serializeToMarkdown()).toBe(
      '# title\n\nciao\n\n\n\nmiao\n\n&nbsp;'
    )
    gridBody.remove()
  })

  test('moves the floating menu when the grid scrolls', async () => {
    const gridBody = document.createElement('div')
    gridBody.className = 'grid-view__body'
    document.body.appendChild(gridBody)

    const wrapper = await testApp.mount(GridViewFieldRichText, {
      attachTo: gridBody,
      props: {
        field,
        value: 'hello',
        selected: true,
        readOnly: false,
        storePrefix: 'page/',
        workspaceId: 10,
      },
      global: {
        stubs: {
          FieldRichTextModal: {
            template: '<div></div>',
            methods: { isOpen: () => false },
          },
        },
      },
    })
    wrapper.vm.edit()
    await new Promise((resolve) => setTimeout(resolve))

    const editor = wrapper.findComponent(RichTextEditor)
    let selectionTop = 200
    let coordinateReads = 0
    editor.vm.editor.view.coordsAtPos = () => {
      coordinateReads++
      return {
        top: selectionTop,
        bottom: selectionTop + 20,
        left: 700,
        right: 700,
      }
    }
    editor.vm.editor.commands.focus()
    editor.vm.editor.commands.setTextSelection(1)
    editor.vm.$refs.root.dispatchEvent(new Event('scroll'))
    await new Promise((resolve) => setTimeout(resolve, 30))

    const initialCoordinateReads = coordinateReads
    selectionTop = 120
    gridBody.dispatchEvent(new Event('scroll'))
    await new Promise((resolve) => setTimeout(resolve, 30))

    expect(coordinateReads).toBeGreaterThan(initialCoordinateReads)
    gridBody.remove()
  })

  test('shows the error and blocks closing while the modal value is over the limit', async () => {
    const wrapper = await mountComponent()
    await editAndExpand(wrapper)
    const modal = wrapper.findComponent(FieldRichTextModal)

    modal.findComponent(RichTextEditorStub).vm.setContent('x'.repeat(15))
    await wrapper.vm.$nextTick()

    const error = modal.find('.rich-text-modal__alert')
    expect(error.exists()).toBe(true)
    expect(error.text()).toBe('fieldErrors.maxCharsExceeded')
    // The close affordance is removed while invalid, so the modal cannot be closed.
    expect(modal.find('.modal__close').exists()).toBe(false)
    expect(wrapper.vm.isModalOpen()).toBe(true)

    modal.findComponent(RichTextEditorStub).vm.setContent('ok')
    await wrapper.vm.$nextTick()

    expect(modal.find('.rich-text-modal__alert').exists()).toBe(false)
    expect(modal.find('.modal__close').exists()).toBe(true)
  })

  describe('image uploads', () => {
    const imageName =
      'Kq3vZ8mPx1LbT7nWc4RdYh2JsF9gAeU6_e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.png'
    const uploadedImage = {
      size: 2048,
      mime_type: 'image/png',
      is_image: true,
      image_width: 640,
      image_height: 480,
      uploaded_at: '2026-09-25T10:00:00.000000+00:00',
      url: `http://localhost:4000/media/user_files/${imageName}`,
      thumbnails: {
        tiny: {
          url: `http://localhost:4000/media/thumbnails/tiny/${imageName}`,
          width: null,
          height: 21,
        },
        small: {
          url: `http://localhost:4000/media/thumbnails/small/${imageName}`,
          width: 48,
          height: 48,
        },
        card_cover: {
          url: `http://localhost:4000/media/thumbnails/card_cover/${imageName}`,
          width: 300,
          height: 160,
        },
      },
      name: imageName,
      original_name: 'sunset.png',
    }

    const uploadRequests = () =>
      testApp.mock.history.post.filter(
        (request) => request.url === '/user-files/upload-file/'
      )

    const mountWithEditor = (props = {}) =>
      testApp.mount(GridViewFieldRichText, {
        props: {
          field,
          value: 'hello',
          selected: true,
          readOnly: false,
          storePrefix: 'page/',
          workspaceId: 10,
          ...props,
        },
        global: {
          stubs: {
            FieldRichTextModal: {
              template: '<div></div>',
              methods: { isOpen: () => false },
            },
          },
        },
      })

    const settle = async () => {
      for (let i = 0; i < 10; i += 1) {
        await new Promise((resolve) => setTimeout(resolve))
      }
    }

    const dropImage = async (wrapper) => {
      const editor = wrapper.findComponent(RichTextEditor)
      // jsdom has no layout, so ProseMirror cannot map the drop coordinates.
      const { view } = editor.vm.editor
      view.posAtCoords = () => ({
        pos: view.state.doc.content.size - 1,
        inside: -1,
      })
      await editor.find('.tiptap').trigger('drop', {
        clientX: 0,
        clientY: 0,
        dataTransfer: {
          files: [new File(['png'], 'sunset.png', { type: 'image/png' })],
          types: ['Files'],
          getData: () => '',
        },
      })
    }

    beforeEach(() => {
      testApp.mock.onPost('/user-files/upload-file/').reply(200, uploadedImage)
    })

    test('uploads an image dropped into the open cell editor and saves its reference', async () => {
      const app = testApp.getApp()
      app.$config.public = {
        ...app.$config.public,
        baserowMaxFieldTextLength: 10000,
      }
      const wrapper = await mountWithEditor()
      wrapper.vm.edit()
      await settle()

      await dropImage(wrapper)
      await vi.waitFor(() =>
        expect(wrapper.find('.tiptap img').exists()).toBe(true)
      )
      await wrapper.setProps({ selected: false })

      expect(uploadRequests()).toHaveLength(1)
      expect(wrapper.emitted('update')).toHaveLength(1)
      const [savedValue, oldValue] = wrapper.emitted('update')[0]
      expect(savedValue).toContain(`![sunset][${imageName}]`)
      expect(savedValue).toContain('hello')
      expect(oldValue).toBe('hello')
    })

    test('does not upload an image dropped on an opened read-only cell', async () => {
      const wrapper = await mountWithEditor({ readOnly: true })
      wrapper.vm.edit()
      await settle()
      expect(wrapper.findComponent(RichTextEditor).exists()).toBe(true)

      await dropImage(wrapper)
      await settle()

      expect(uploadRequests()).toHaveLength(0)
      expect(wrapper.find('.tiptap img').exists()).toBe(false)
    })
  })
})
