import { defineAsyncComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldRichText from '@baserow/modules/database/components/view/grid/fields/GridViewFieldRichText'
import FieldRichTextModal from '@baserow/modules/database/components/view/FieldRichTextModal'
import FormViewDescription from '@baserow/modules/database/components/view/form/FormViewDescription'

const Editor = {
  name: 'RichTextEditor',
  props: { modelValue: { type: [String, Object], default: '' } },
  emits: ['update:modelValue', 'blur'],
  data() {
    return { content: this.modelValue }
  },
  template: `
    <textarea
      class="async-editor-test-input"
      :value="content"
      @input="content = $event.target.value; $emit('update:modelValue', content)"
      @blur="$emit('blur')"
    />
  `,
  methods: {
    focus() {
      this.$el.focus()
    },
    serializeToMarkdown() {
      return this.content
    },
    isEventTargetInside(event) {
      return this.$el.contains(event.target)
    },
  },
}

// Each case starts with an uncached chunk and resolves it only after the user
// opens, expands or closes the editor. Ordinary eager stubs miss these races.
const delayedEditor = () => {
  let resolve
  let reject
  const component = defineAsyncComponent(
    () =>
      new Promise((finish, fail) => {
        resolve = finish
        reject = fail
      })
  )
  return {
    component,
    finish: () => resolve(Editor),
    fail: (error) => reject(error),
  }
}

const withEditor = (component, editor) => ({
  ...component,
  components: { ...component.components, RichTextEditor: editor },
})

describe('async rich text editors', () => {
  let testApp

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

  const mountGrid = (editor, global = {}) =>
    testApp.mount(
      {
        ...withEditor(GridViewFieldRichText, editor),
        components: {
          ...GridViewFieldRichText.components,
          RichTextEditor: editor,
          FieldRichTextModal: withEditor(FieldRichTextModal, editor),
        },
      },
      {
        props: {
          field,
          value: 'hello',
          selected: true,
          readOnly: false,
          storePrefix: 'page/',
          workspaceId: 10,
        },
        global,
      }
    )

  const finishLoading = async (loader) => {
    loader.finish()
    await flushPromises()
  }

  test('focuses an inline cell after its first editor chunk mounts', async () => {
    const loader = delayedEditor()
    const wrapper = await mountGrid(loader.component)
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('textarea').exists()).toBe(false)
    await finishLoading(loader)

    expect(document.activeElement).toBe(wrapper.find('textarea').element)
    expect(wrapper.find('textarea').element.value).toBe('hello')
  })

  test('expands a cell before the editor chunk loads and saves no empty value', async () => {
    const loader = delayedEditor()
    const wrapper = await mountGrid(loader.component)
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()

    await wrapper
      .find('.grid-field-rich-text__textarea-expand-icon')
      .trigger('click')
    expect(document.querySelector('.rich-text-modal')).not.toBeNull()
    expect(document.querySelector('.async-editor-test-input')).toBeNull()

    document
      .querySelector('.rich-text-modal')
      .closest('.modal__box')
      .querySelector('.modal__close')
      .click()
    await new Promise((resolve) => setTimeout(resolve))
    await wrapper.vm.$nextTick()
    await finishLoading(loader)

    expect(wrapper.emitted('update')).toBeUndefined()
    expect(document.querySelector('.rich-text-modal')).toBeNull()
  })

  test('does not take focus when a pending cell is unselected', async () => {
    const loader = delayedEditor()
    const wrapper = await mountGrid(loader.component)
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()
    await wrapper.setProps({ selected: false })
    await finishLoading(loader)

    expect(wrapper.find('textarea').exists()).toBe(false)
    expect(wrapper.emitted('update')).toBeUndefined()
  })

  test('keeps the cell value after a failed chunk and retries when reopened', async () => {
    const loader = delayedEditor()
    const errors = []
    const wrapper = await mountGrid(loader.component, {
      config: { errorHandler: (error) => errors.push(error) },
    })
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()
    const error = new Error('Editor chunk unavailable')
    loader.fail(error)
    await flushPromises()

    expect(errors).toEqual([error])
    await wrapper.setProps({ selected: false })
    expect(wrapper.emitted('update')).toBeUndefined()

    await wrapper.setProps({ selected: true })
    wrapper.vm.edit()
    await wrapper.vm.$nextTick()
    await finishLoading(loader)

    const input = wrapper.find('textarea')
    expect(input.element.value).toBe('hello')
    expect(document.activeElement).toBe(input.element)
  })

  test('focuses the expanded editor after its first chunk mounts', async () => {
    const loader = delayedEditor()
    const wrapper = await testApp.mount(
      withEditor(FieldRichTextModal, loader.component),
      { props: { field, modelValue: 'hello' } }
    )
    wrapper.vm.toggle()
    await wrapper.vm.$nextTick()
    await finishLoading(loader)

    const input = document.querySelector('.async-editor-test-input')
    expect(input.value).toBe('hello')
    expect(document.activeElement).toBe(input)
  })

  test('focuses a form description after its chunk mounts and saves the edit', async () => {
    const loader = delayedEditor()
    const wrapper = await testApp.mount(
      withEditor(FormViewDescription, loader.component),
      { props: { value: '', placeholder: 'Description' } }
    )
    await wrapper.find('.form-view__description-placeholder').trigger('click')
    await finishLoading(loader)
    const input = wrapper.find('textarea')

    expect(document.activeElement).toBe(input.element)
    await input.setValue('A new description')
    await input.trigger('blur')

    expect(wrapper.emitted('change')).toEqual([['A new description']])
  })
})
