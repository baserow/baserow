import { mountSuspended } from '@nuxt/test-utils/runtime'
import ChoiceElement from '@baserow/modules/builder/components/elements/components/ChoiceElement.vue'

describe('ChoiceElement', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = useNuxtApp()
    store = testApp.$store
  })

  const mountComponent = ({ props = {}, slots = {}, provide = {} }) => {
    return mountSuspended(ChoiceElement, {
      props: props,
      slots,
      global: { provide },
    })
  }

  const mountComponentForElement = async (element) => {
    const page = { id: 1, elements: [] }
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const workspace = {}
    const mode = 'public'
    const applicationContext = { builder, page, mode }

    store.dispatch('element/forceCreate', { page, element })

    const elementType = store.$registry.get('element', 'choice')

    const defaultValue = element.multiple ? [] : null
    const payload = {
      value: defaultValue,
      type: elementType.formDataType(element),
      isValid: elementType.isValid(element, defaultValue, applicationContext),
      touched: false,
    }

    store.dispatch('formData/setFormData', {
      page,
      elementId: element.id,
      payload,
    })

    const wrapper = await mountComponent({
      props: {
        element,
      },
      provide: {
        builder,
        currentPage: page,
        elementPage: page,
        mode,
        applicationContext: { builder, page, mode },
        element,
        workspace,
      },
    })
    return wrapper
  }

  test('as default', async () => {
    const wrapper = await mountComponentForElement({
      id: 42,
      defaultValue: '1',
      type: 'choice',
      multiple: false,
      option_type: 'manual',
      show_as_dropdown: true,
      options: [],
      page_id: 1,
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('as manual dropdown', async () => {
    const wrapper = await mountComponentForElement({
      id: 42,
      defaultValue: '1',
      type: 'choice',
      multiple: false,
      option_type: 'manual',
      show_as_dropdown: true,
      options: [
        { value: '1', name: 'First' },
        { value: '2', name: 'Second' },
      ],
      page_id: 1,
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('as manual dropdown - values', async () => {
    const wrapper = await mountComponentForElement({
      id: 42,
      defaultValue: '1',
      type: 'choice',
      multiple: false,
      option_type: 'manual',
      show_as_dropdown: true,
      options: [
        { value: '', name: 'Foo Name' },
        { value: 'bar_name', name: 'Bar Name' },
        { value: null, name: 'Baz Name' },
      ],
      page_id: 1,
    })

    expect(wrapper.vm.optionsResolved).toEqual([
      // An empty string is a valid Value
      { value: '', name: 'Foo Name' },
      // 'bar_name' is a valid Value
      { value: 'bar_name', name: 'Bar Name' },
      // null is replaced by the name, i.e. 'Baz Name'
      { value: 'Baz Name', name: 'Baz Name' },
    ])
  })

  test('as manual radio', async () => {
    const wrapper = await mountComponentForElement({
      id: 42,
      defaultValue: '1',
      type: 'choice',
      multiple: false,
      option_type: 'manual',
      show_as_dropdown: false,
      options: [
        { value: '1', name: 'First' },
        { value: '2', name: 'Second' },
      ],
      page_id: 1,
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('as manual checkboxes', async () => {
    const wrapper = await mountComponentForElement({
      id: 42,
      defaultValue: '1',
      type: 'choice',
      multiple: true,
      option_type: 'manual',
      show_as_dropdown: false,
      options: [
        { value: '1', name: 'First' },
        { value: '2', name: 'Second' },
      ],
      page_id: 1,
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  describe('with formula options', () => {
    const formulaOptionsElement = (overrides = {}) => ({
      id: 43,
      type: 'choice',
      multiple: false,
      option_type: 'formulas',
      show_as_dropdown: true,
      options: [],
      formula_value: { formula: "'a,b'" },
      formula_name: { formula: "'**A**,**B**'", format: 'markdown' },
      default_value: { formula: "'a'" },
      page_id: 1,
      ...overrides,
    })

    test('renders markdown option names in the dropdown', async () => {
      const wrapper = await mountComponentForElement(formulaOptionsElement())

      const items = wrapper.findAll('.ab-dropdownitem__item-name-text')
      expect(items.map((item) => item.find('strong').text())).toEqual([
        'A',
        'B',
      ])
      // The tooltip keeps the raw name.
      expect(items.map((item) => item.attributes('title'))).toEqual([
        '**A**',
        '**B**',
      ])
      // The selected option is rendered too, not shown as raw syntax.
      const selected = wrapper.find('.ab-dropdown__selected-text')
      expect(selected.find('strong').text()).toBe('A')
      expect(selected.text()).toBe('A')
    })

    test('lists the selected options of a multiple dropdown', async () => {
      const wrapper = await mountComponentForElement(
        formulaOptionsElement({
          multiple: true,
          default_value: { formula: "'a,b'" },
        })
      )

      const selected = wrapper.find('.ab-dropdown__selected-text')
      expect(selected.findAll('strong').map((name) => name.text())).toEqual([
        'A',
        'B',
      ])
      expect(selected.text()).toBe('A, B')
    })

    test('keeps plain option names as they are', async () => {
      const wrapper = await mountComponentForElement(
        formulaOptionsElement({ formula_name: { formula: "'**A**,**B**'" } })
      )

      const items = wrapper.findAll('.ab-dropdownitem__item-name-text')
      expect(items.map((item) => item.text())).toEqual(['**A**', '**B**'])
      expect(wrapper.find('strong').exists()).toBe(false)
    })

    test('renders markdown option names as radios', async () => {
      const wrapper = await mountComponentForElement(
        formulaOptionsElement({ show_as_dropdown: false })
      )

      const labels = wrapper.findAll('.ab-radio__label')
      expect(labels.map((label) => label.find('strong').text())).toEqual([
        'A',
        'B',
      ])
    })

    test('renders markdown option names as checkboxes', async () => {
      const wrapper = await mountComponentForElement(
        formulaOptionsElement({ show_as_dropdown: false, multiple: true })
      )

      const labels = wrapper.findAll('.ab-checkbox__label')
      expect(labels.map((label) => label.find('strong').text())).toEqual([
        'A',
        'B',
      ])
    })

    test('never renders links in option names', async () => {
      const wrapper = await mountComponentForElement(
        formulaOptionsElement({
          formula_name: {
            formula: "'[A](https://baserow.io),B'",
            format: 'markdown',
          },
        })
      )

      expect(wrapper.find('a.ab-link').exists()).toBe(false)
      expect(wrapper.find('.ab-dropdownitem__item-name-text').text()).toBe(
        '[A](https://baserow.io)'
      )
    })
  })
})
