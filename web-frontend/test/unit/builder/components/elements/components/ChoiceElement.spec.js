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
})

describe('ChoiceElement Markdown', () => {
  let store = null

  beforeEach(() => {
    store = useNuxtApp().$store
  })

  // The selection is driven by `default_value`: the form element mixin resets
  // the form data to the resolved default value on mount.
  const mountChoice = async (elementOverrides, value = null) => {
    const page = { id: 1, elements: [] }
    const builder = { id: 1, theme: { primary_color: '#ccc' }, pages: [page] }
    const mode = 'public'
    const applicationContext = { builder, page, mode }
    const element = {
      id: 43,
      type: 'choice',
      label: { mode: 'raw', formula: 'Pick **one** ([help](/help))' },
      label_format: 'plain',
      default_value: { formula: '' },
      placeholder: { formula: '' },
      required: false,
      multiple: false,
      show_as_dropdown: false,
      option_type: 'manual',
      option_format: 'plain',
      options: [
        { id: 1, value: '1', name: '**First**' },
        { id: 2, value: '2', name: 'See [docs](https://example.com)' },
      ],
      page_id: page.id,
      styles: {},
      ...elementOverrides,
    }

    store.dispatch('element/forceCreate', { page, element })
    const elementType = store.$registry.get('element', 'choice')
    store.dispatch('formData/setFormData', {
      page,
      elementId: element.id,
      payload: {
        value,
        type: elementType.formDataType(element),
        isValid: elementType.isValid(element, value, applicationContext),
        touched: false,
      },
    })

    return mountSuspended(ChoiceElement, {
      props: { element },
      global: {
        provide: {
          builder,
          currentPage: page,
          elementPage: page,
          mode,
          applicationContext,
          element,
          workspace: {},
        },
      },
    })
  }

  test('renders the label as Markdown with links', async () => {
    const wrapper = await mountChoice({ label_format: 'markdown' })

    const label = wrapper.find('.ab-form-group__label')
    expect(label.find('strong').text()).toBe('one')
    expect(label.find('a.ab-link').attributes('href')).toBe('/help')
  })

  test('renders plain option names as-is', async () => {
    const wrapper = await mountChoice({})

    const [first] = wrapper.findAll('.ab-radio__label')
    expect(first.find('strong').exists()).toBe(false)
    expect(first.text()).toBe('**First**')
  })

  test('renders radio option names as inline Markdown without links', async () => {
    const wrapper = await mountChoice({ option_format: 'markdown' })

    const [first, second] = wrapper.findAll('.ab-radio__label')
    expect(first.find('strong').text()).toBe('First')
    expect(second.find('a').exists()).toBe(false)
    expect(second.text()).toBe('See [docs](https://example.com)')
  })

  test('renders checkbox option names as inline Markdown', async () => {
    const wrapper = await mountChoice(
      { option_format: 'markdown', multiple: true },
      []
    )

    const [first] = wrapper.findAll('.ab-checkbox__label')
    expect(first.find('strong').text()).toBe('First')
  })

  test('renders dropdown option names as inline Markdown, keeping the raw name as tooltip', async () => {
    const wrapper = await mountChoice(
      {
        option_format: 'markdown',
        show_as_dropdown: true,
        default_value: { mode: 'raw', formula: '1' },
      },
      '1'
    )

    const [first, second] = wrapper.findAll('.ab-dropdownitem__item-name-text')
    expect(first.find('strong').text()).toBe('First')
    expect(first.attributes('title')).toBe('**First**')
    expect(second.find('a').exists()).toBe(false)

    // The collapsed dropdown shows the selected option rendered as well. The
    // dropdown resolves its selection once the items have registered.
    await wrapper.vm.$nextTick()
    const selected = wrapper.find('.ab-dropdown__selected-text')
    expect(selected.find('strong').text()).toBe('First')
  })

  test('renders every selected option in a multiple Markdown dropdown', async () => {
    const wrapper = await mountChoice(
      {
        option_format: 'markdown',
        show_as_dropdown: true,
        multiple: true,
        default_value: { mode: 'raw', formula: '1,2' },
      },
      ['1', '2']
    )

    await wrapper.vm.$nextTick()
    const selected = wrapper.find('.ab-dropdown__selected-text')
    expect(selected.find('strong').text()).toBe('First')
    expect(selected.text()).toBe('First, See [docs](https://example.com)')
  })
})
