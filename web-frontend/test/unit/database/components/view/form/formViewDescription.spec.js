import { TestApp } from '@baserow/test/helpers/testApp'
import FormViewDescription from '@baserow/modules/database/components/view/form/FormViewDescription'

// Stub the tiptap editor: serialized output tracks live content, mirroring the
// real component without pulling tiptap into the jsdom test.
const RichTextEditorStub = {
  name: 'RichTextEditor',
  props: {
    modelValue: { type: [String, Object], default: '' },
    editable: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'blur'],
  data() {
    return { content: this.modelValue || '' }
  },
  template: '<div class="rich-text-editor-stub"></div>',
  methods: {
    focus() {},
    setContent(value) {
      this.content = value
      this.$emit('update:modelValue', value)
    },
    serializeToMarkdown() {
      // Mirror tiptap-markdown, which escapes stray markdown-special chars
      // (e.g. a lone "*") so serialized output can differ from the raw stored
      // string even when the user never edited anything.
      return (this.content || '').replace(/\*/g, '\\*')
    },
  },
}

describe('FormViewDescription', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (props = {}) =>
    testApp.mount(FormViewDescription, {
      props: {
        value: '',
        readOnly: false,
        placeholder: 'Add a description',
        ...props,
      },
      global: { stubs: { RichTextEditor: RichTextEditorStub } },
    })

  const startEditing = async (wrapper) => {
    await wrapper.find('.form-view__edit').trigger('click')
    await wrapper.vm.$nextTick()
    return wrapper.findComponent(RichTextEditorStub)
  }

  test('renders the stored description read-only in display mode', async () => {
    const wrapper = await mountComponent({ value: '**bold**' })
    const editor = wrapper.findComponent(RichTextEditorStub)
    expect(editor.exists()).toBe(true)
    expect(editor.props('modelValue')).toBe('**bold**')
    expect(editor.props('editable')).toBe(false)
  })

  test('shows an edit affordance when not read only and hides it when read only', async () => {
    const editable = await mountComponent({
      value: '**bold**',
      readOnly: false,
    })
    expect(editable.find('.form-view__edit').exists()).toBe(true)

    const readOnly = await mountComponent({ value: '**bold**', readOnly: true })
    expect(readOnly.find('.form-view__edit').exists()).toBe(false)
  })

  test('mounts the editable editor only after entering edit mode', async () => {
    const wrapper = await mountComponent({ value: '' })
    // Nothing to render for an empty value: only the placeholder is shown.
    expect(wrapper.findComponent(RichTextEditorStub).exists()).toBe(false)
    const editor = await startEditing(wrapper)
    expect(editor.exists()).toBe(true)
    expect(editor.props('editable')).toBe(true)
  })

  test('emits change with markdown after an edit and blur', async () => {
    const wrapper = await mountComponent({ value: '' })
    const editor = await startEditing(wrapper)
    editor.vm.setContent('See [docs](https://baserow.io)')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    const events = wrapper.emitted('change')
    expect(events).toBeTruthy()
    expect(events[events.length - 1][0]).toBe('See [docs](https://baserow.io)')
  })

  test('does not emit change on blur without an edit, even when markdown serialization differs from a legacy value', async () => {
    const wrapper = await mountComponent({
      value: 'Rate 1-5 and use * bullets',
    })
    const editor = await startEditing(wrapper)
    // Focus in and out without changing anything (blur only, no update).
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('change')).toBeFalsy()
  })

  test('emits change after a real edit of a legacy plain-text value', async () => {
    const wrapper = await mountComponent({
      value: 'Rate 1-5 and use * bullets',
    })
    const editor = await startEditing(wrapper)
    editor.vm.setContent('A whole new description')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    const events = wrapper.emitted('change')
    expect(events).toBeTruthy()
    expect(events[events.length - 1][0]).toBe('A whole new description')
  })

  test('keeps the in-progress edit when the value prop changes externally', async () => {
    const wrapper = await mountComponent({ value: 'original' })
    const editor = await startEditing(wrapper)
    editor.vm.setContent('unsaved edit in progress')
    await wrapper.vm.$nextTick()

    // A realtime update to the stored value arrives mid-edit.
    await wrapper.setProps({ value: 'external change' })

    // The unsaved edit is preserved: blur still serializes what was typed, not
    // the external value.
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()
    const events = wrapper.emitted('change')
    expect(events[events.length - 1][0]).toBe('unsaved edit in progress')
  })

  test('read only mode does not enter edit mode', async () => {
    const wrapper = await mountComponent({ value: 'read only', readOnly: true })
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent(RichTextEditorStub).props('editable')).toBe(
      false
    )
  })
})
