import { TestApp } from '@baserow/test/helpers/testApp'
import FormPageField from '@baserow/modules/database/components/view/form/FormPageField'

// Read-only stub: exposes the markdown handed to the editor so we can assert it is
// forwarded for rendering (the real editor parses markdown; tiptap is out of scope
// here). FormPageField renders through FormViewDescription's read-only branch; the
// stub is applied deeply, so it replaces the editor inside it.
const RichTextEditorStub = {
  name: 'RichTextEditor',
  props: {
    modelValue: { type: [String, Object], default: '' },
    editable: { type: Boolean, default: true },
  },
  template:
    '<div class="rich-text-editor-stub" :data-editable="editable">{{ modelValue }}</div>',
}

describe('FormPageField description render', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const baseField = {
    field: { id: 1, name: 'Name', type: 'text' },
    field_component: 'default',
    required: false,
    _: { touched: false },
  }

  const mountComponent = (description) =>
    testApp.mount(FormPageField, {
      props: {
        slug: 'abc',
        value: '',
        field: { ...baseField, description },
      },
      global: { stubs: { RichTextEditor: RichTextEditorStub } },
    })

  test('renders the description read-only through the editor', async () => {
    const wrapper = await mountComponent('**bold**')
    const editor = wrapper.findComponent(RichTextEditorStub)
    expect(editor.exists()).toBe(true)
    expect(editor.props('editable')).toBe(false)
    expect(editor.props('modelValue')).toBe('**bold**')
  })

  test('renders nothing when there is no description', async () => {
    const wrapper = await mountComponent('')
    expect(wrapper.findComponent(RichTextEditorStub).exists()).toBe(false)
  })

  test('forwards legacy plain-text descriptions unchanged (backward compat)', async () => {
    const wrapper = await mountComponent('Just plain text')
    expect(wrapper.findComponent(RichTextEditorStub).props('modelValue')).toBe(
      'Just plain text'
    )
  })
})
