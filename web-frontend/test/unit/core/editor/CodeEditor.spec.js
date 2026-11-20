import { mountSuspended } from '@nuxt/test-utils/runtime'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { EditorContent } from '@tiptap/vue-3'

import CodeEditor from '@baserow/modules/core/components/CodeEditor'

enableAutoUnmount(afterEach)

test('edits HTML source in the inline and expanded editors with shared text and blur events', async () => {
  const title = 'Custom HTML in head'
  const placeholder = 'Paste head HTML...'
  let wrapper
  wrapper = await mountSuspended(CodeEditor, {
    props: {
      language: 'html',
      modelValue: '',
      modalTitle: title,
      placeholder,
      'onUpdate:modelValue': (code) => wrapper.setProps({ modelValue: code }),
    },
  })

  await vi.waitFor(() =>
    expect(wrapper.find('.code-editor .tiptap').exists()).toBe(true)
  )
  expect(
    wrapper.get('.code-editor .is-editor-empty').attributes('data-placeholder')
  ).toBe(placeholder)

  await wrapper.get(`button[aria-label="${title}"]`).trigger('click')
  await vi.waitFor(() =>
    expect(wrapper.find('.code-editor--modal .tiptap').exists()).toBe(true)
  )
  expect(wrapper.get('.modal__box--wide .box__title').text()).toBe(title)
  expect(
    wrapper
      .get('.code-editor--modal .is-editor-empty')
      .attributes('data-placeholder')
  ).toBe(placeholder)

  const source =
    '\n  <meta name="description" content="Literal &amp; source">\n' +
    '<script>window.example = "value"</script>\n'
  await wrapper.setProps({ modelValue: source })
  const inline = wrapper.get('.code-editor .tiptap')
  const expanded = wrapper.get('.code-editor--modal .tiptap')
  expect(inline.attributes('aria-label')).toBe(title)
  expect(expanded.attributes('aria-label')).toBe(title)
  expect(inline.element.textContent).toBe(source)
  expect(expanded.element.textContent).toBe(source)
  expect(inline.find('.hljs-tag').exists()).toBe(true)
  expect(inline.find('meta, script').exists()).toBe(false)
  expect(wrapper.emitted('update:modelValue')).toBeUndefined()

  const editors = wrapper.findAllComponents(EditorContent)
  // Use Tiptap's public commands to drive each real editor instance.
  editors[0]
    .props('editor')
    .commands.insertContentAt(1, { type: 'text', text: '<!-- inline -->\n' })
  await flushPromises()
  const inlineChange = `<!-- inline -->\n${source}`
  expect(wrapper.emitted('update:modelValue')).toEqual([[inlineChange]])
  expect(inline.element.textContent).toBe(inlineChange)
  expect(expanded.element.textContent).toBe(inlineChange)

  editors[1]
    .props('editor')
    .commands.insertContentAt(1, { type: 'text', text: '<!-- expanded -->\n' })
  await flushPromises()
  const expandedChange = `<!-- expanded -->\n${inlineChange}`
  expect(wrapper.emitted('update:modelValue')).toEqual([
    [inlineChange],
    [expandedChange],
  ])
  expect(inline.element.textContent).toBe(expandedChange)
  expect(expanded.element.textContent).toBe(expandedChange)

  const previousBlurs = wrapper.emitted('blur')?.length ?? 0
  await inline.trigger('blur')
  await expanded.trigger('blur')
  expect(wrapper.emitted('blur')).toHaveLength(previousBlurs + 2)

  await wrapper.setProps({ errorMessage: 'Could not save the HTML.' })
  expect(wrapper.get('.code-editor__modal').text()).toContain(
    'Could not save the HTML.'
  )

  await wrapper.get('.code-editor__modal .modal__close').trigger('click')
  await vi.waitFor(() =>
    expect(wrapper.find('.code-editor--modal').exists()).toBe(false)
  )
  expect(wrapper.emitted('blur').length).toBeGreaterThan(previousBlurs + 2)
  await wrapper.get(`button[aria-label="${title}"]`).trigger('click')
  expect(wrapper.get('.code-editor--modal .tiptap').element.textContent).toBe(
    expandedChange
  )
})
