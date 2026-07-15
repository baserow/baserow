import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRichText'
import FieldRichTextModal from '@baserow/modules/database/components/view/FieldRichTextModal'

// Stubbing the tiptap-backed editor keeps the test focused on the modal flow. Like
// the real editor, its serialized output reflects live content, not the lagging prop.
const RichTextEditorStub = {
  name: 'RichTextEditor',
  props: { modelValue: { type: [String, Object], default: '' } },
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

  test('lets TipTap handle paste events while editing', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.vm.onPaste()).toBe(false)

    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.onPaste()).toBe(true)
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
})
