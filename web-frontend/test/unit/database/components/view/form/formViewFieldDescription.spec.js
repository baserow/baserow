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
      return this.content || ''
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

  test('emits updated-field-options with markdown on blur', async () => {
    const wrapper = await mountComponent({ description: '' })
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
})
