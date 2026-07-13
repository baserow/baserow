import { TestApp } from '@baserow/test/helpers/testApp'
import FormViewField from '@baserow/modules/database/components/view/form/FormViewField'

// Stub the tiptap editor: serialized output tracks live content, mirroring the real
// component without pulling tiptap into the jsdom test.
const RichTextEditorStub = {
  name: 'RichTextEditor',
  props: { modelValue: { type: [String, Object], default: '' } },
  emits: ['update:modelValue', 'blur'],
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
      // Mirror tiptap-markdown, which escapes stray markdown-special chars
      // (e.g. a lone "*") so serialized output can differ from the raw
      // stored string even when the user never edited anything.
      return (this.content || '').replace(/\*/g, '\\*')
    },
  },
}

describe('FormViewField description editor', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const field = {
    id: 1,
    name: 'Name',
    type: 'text',
    _: { type: { iconClass: '' } },
  }

  const mountComponent = (fieldOptions = {}) =>
    testApp.mount(FormViewField, {
      props: {
        database: { workspace: { id: 1 } },
        table: { id: 1 },
        view: { slug: 'abc' },
        field,
        fields: [field],
        fieldOptions: {
          description: '**bold**',
          conditions: [],
          condition_groups: [],
          ...fieldOptions,
        },
        readOnly: false,
      },
      global: { stubs: { RichTextEditor: RichTextEditorStub } },
    })

  test('seeds the editor from the stored markdown description', async () => {
    const wrapper = await mountComponent({ description: '**bold**' })
    const editor = wrapper.findComponent(RichTextEditorStub)
    expect(editor.exists()).toBe(true)
    expect(editor.props('modelValue')).toBe('**bold**')
  })

  test('does not mount an editor for an unselected field with no description', async () => {
    const wrapper = await mountComponent({ description: '' })
    // v-if keeps the heavy rich-text editor out of the DOM until needed.
    expect(wrapper.findComponent(RichTextEditorStub).exists()).toBe(false)
    await wrapper.find('.form-view__field').trigger('click')
    expect(wrapper.findComponent(RichTextEditorStub).exists()).toBe(true)
  })

  test('emits updated-field-options with markdown on blur', async () => {
    const wrapper = await mountComponent({ description: '' })
    // With no description the editor only mounts once the field is selected.
    await wrapper.find('.form-view__field').trigger('click')
    const editor = wrapper.findComponent(RichTextEditorStub)
    editor.vm.setContent('See [docs](https://baserow.io)')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    const events = wrapper.emitted('updated-field-options')
    expect(events).toBeTruthy()
    expect(events[events.length - 1][0]).toEqual({
      description: 'See [docs](https://baserow.io)',
    })
  })

  test(
    'does not emit on blur without an edit, even if markdown serialization ' +
      'differs from the stored legacy plain-text value',
    async () => {
      const wrapper = await mountComponent({
        description: 'Rate 1-5 and use * bullets',
      })
      const editor = wrapper.findComponent(RichTextEditorStub)
      // No edit happened, just focus in/out (blur only, no update:modelValue).
      editor.vm.$emit('blur')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('updated-field-options')).toBeFalsy()
    }
  )

  test('emits on blur after a real edit even for a legacy plain-text description', async () => {
    const wrapper = await mountComponent({
      description: 'Rate 1-5 and use * bullets',
    })
    const editor = wrapper.findComponent(RichTextEditorStub)
    editor.vm.setContent('A whole new description')
    editor.vm.$emit('blur')
    await wrapper.vm.$nextTick()

    const events = wrapper.emitted('updated-field-options')
    expect(events).toBeTruthy()
    expect(events[events.length - 1][0]).toEqual({
      description: 'A whole new description',
    })
  })

  test('keeps an in-progress edit when the stored description changes externally', async () => {
    const wrapper = await mountComponent({ description: 'original' })
    const editor = wrapper.findComponent(RichTextEditorStub)
    // User starts editing (this marks the buffer dirty).
    editor.vm.setContent('unsaved edit in progress')
    await wrapper.vm.$nextTick()

    // A realtime update to the stored value arrives mid-edit.
    await wrapper.setProps({
      fieldOptions: {
        description: 'external change',
        conditions: [],
        condition_groups: [],
      },
    })

    // The unsaved edit is preserved, not clobbered by the external value.
    expect(wrapper.findComponent(RichTextEditorStub).props('modelValue')).toBe(
      'unsaved edit in progress'
    )
  })
})
