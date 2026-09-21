import { mountSuspended } from '@nuxt/test-utils/runtime'
import { reactive, nextTick } from 'vue'

describe('form element validation', () => {
  let store
  const wrappers = []

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  afterEach(() => {
    wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  const mountElement = async (overrides = {}, { insideForm = false } = {}) => {
    const page = reactive({
      id: 1,
      elements: [],
      graph: insideForm
        ? { 0: 41, 41: { children: { '': [42] } }, 42: {} }
        : { 0: 42, 42: {} },
    })
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const mode = 'public'
    const element = reactive({
      id: 42,
      type: 'input_text',
      validation_type: 'text',
      default_value: { formula: '' },
      label: { formula: '' },
      placeholder: { formula: '' },
      required: true,
      input_type: 'text',
      is_multiline: false,
      rows: 1,
      page_id: page.id,
      styles: {},
      ...overrides,
    })
    if (insideForm) {
      await store.dispatch('element/forceCreate', {
        page,
        element: { id: 41, type: 'form_container' },
      })
    }
    await store.dispatch('element/forceCreate', { page, element })
    const wrapper = await mountSuspended(
      store.$registry.get('element', element.type).component,
      {
        props: { element },
        global: {
          provide: {
            builder,
            currentPage: page,
            elementPage: page,
            mode,
            applicationContext: { builder, page, mode },
            element,
            workspace: {},
          },
        },
      }
    )
    wrappers.push(wrapper)
    return { wrapper, element, page }
  }

  const choice = {
    type: 'choice',
    multiple: true,
    option_type: 'manual',
    show_as_dropdown: false,
    options: [{ id: 1, value: 'one', name: 'One' }],
  }
  const errorSelector = '.ab-form-group__error-message'

  test.each([
    ['text', {}],
    ['checkbox', { type: 'checkbox' }],
    ['choice checkboxes', choice],
    ['choice dropdown', { ...choice, show_as_dropdown: true }],
  ])('%s starts without a required error', async (_, overrides) => {
    const { wrapper } = await mountElement(overrides)
    expect(wrapper.find(errorSelector).exists()).toBe(false)
  })

  test('text validates on blur and clears the error when corrected', async () => {
    const { wrapper } = await mountElement()
    await wrapper.get('input').setValue('value')
    await wrapper.get('input').setValue('')
    expect(wrapper.find(errorSelector).exists()).toBe(false)
    await wrapper.get('input').trigger('blur')
    expect(wrapper.get(errorSelector).text()).toContain('error.requiredField')
    await wrapper.get('input').setValue('value')
    expect(wrapper.find(errorSelector).exists()).toBe(false)
  })

  test.each([
    ['checkbox', { type: 'checkbox' }],
    ['choice checkboxes', choice],
  ])('%s validates after user changes', async (_, overrides) => {
    const { wrapper } = await mountElement(overrides)
    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(wrapper.find(errorSelector).exists()).toBe(false)
    await wrapper.get('input[type="checkbox"]').setValue(false)
    expect(wrapper.get(errorSelector).text()).toContain('error.requiredField')
  })

  test('formula defaults changing do not touch the input', async () => {
    const { wrapper, element } = await mountElement({
      default_value: { formula: "'initial'" },
    })
    expect(wrapper.get('input').element.value).toBe('initial')
    element.default_value = { formula: '' }
    await nextTick()
    expect(wrapper.get('input').element.value).toBe('')
    expect(wrapper.find(errorSelector).exists()).toBe(false)
    await wrapper.get('input').trigger('blur')
    expect(wrapper.get(errorSelector).text()).toContain('error.requiredField')
  })

  test('choice dropdown validates when closed without a selection', async () => {
    const { wrapper } = await mountElement({
      ...choice,
      show_as_dropdown: true,
    })
    await wrapper.get('.ab-dropdown__selected').trigger('click')
    expect(wrapper.find(errorSelector).exists()).toBe(false)
    await wrapper.get('.ab-dropdown').trigger('focusout', {
      relatedTarget: document.body,
    })
    expect(wrapper.get(errorSelector).text()).toContain('error.requiredField')
  })

  test('resetting form data does not touch the input again', async () => {
    const { wrapper, page } = await mountElement()
    await wrapper.get('input').setValue('value')
    await wrapper.get('input').trigger('blur')
    await store.dispatch('formData/setFormData', {
      page,
      uniqueElementId: '42',
      payload: { value: '', touched: false, isValid: false },
    })
    await nextTick()
    expect(wrapper.get('input').element.value).toBe('')
    expect(wrapper.find(errorSelector).exists()).toBe(false)
  })

  test('date input validates after blur', async () => {
    const { wrapper } = await mountElement({
      type: 'datetime_picker',
      date_format: 'ISO',
      time_format: '24',
      include_time: false,
    })
    expect(wrapper.find(errorSelector).exists()).toBe(false)
    await wrapper.get('input').setValue('invalid date')
    await wrapper.get('input').trigger('blur')
    expect(wrapper.find(errorSelector).exists()).toBe(true)
  })

  test('checkbox in a form waits for form validation', async () => {
    const { wrapper, page } = await mountElement(
      { type: 'checkbox' },
      { insideForm: true }
    )
    await wrapper.get('input').setValue(true)
    await wrapper.get('input').setValue(false)
    expect(wrapper.find(errorSelector).exists()).toBe(false)
    await store.dispatch('formData/setElementTouched', {
      page,
      uniqueElementId: '42',
      wasTouched: true,
    })
    expect(wrapper.get(errorSelector).text()).toContain('error.requiredField')
  })
})
