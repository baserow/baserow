import { mountSuspended } from '@nuxt/test-utils/runtime'
import { DOMWrapper } from '@vue/test-utils'
import ChoiceElement from '@baserow/modules/builder/components/elements/components/ChoiceElement.vue'

describe('ChoiceElement', () => {
  let testApp = null
  let store = null
  let wrappers = []

  beforeEach(() => {
    testApp = useNuxtApp()
    store = testApp.$store
  })

  afterEach(() => {
    wrappers.forEach((wrapper) => wrapper.unmount())
    wrappers = []
  })

  const mountComponent = async ({ props = {}, slots = {}, provide = {} }) => {
    const wrapper = await mountSuspended(ChoiceElement, {
      props: props,
      slots,
      global: { provide },
    })
    wrappers.push(wrapper)
    return wrapper
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

    for (const [index, value] of ['', 'bar_name', 'Baz Name'].entries()) {
      await wrapper.get('.ab-dropdown__selected').trigger('click')
      await wrapper
        .findAll('.ab-dropdownitem__item-link')
        .at(index)
        .trigger('click')

      expect(
        wrapper
          .findComponent({ name: 'ABDropdown' })
          .emitted('update:modelValue')
          .at(-1)
      ).toEqual([value])
    }
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

  describe('dropdown search', () => {
    const options = [
      { value: 'value-1', name: 'Alpha Supplier' },
      { value: 'value-2', name: 'Beta Supplier' },
      { value: 'value-3', name: 'Gamma Partner' },
    ]

    const mountSearchableChoice = (values = {}) =>
      mountComponentForElement({
        id: 42,
        type: 'choice',
        page_id: 1,
        multiple: false,
        show_as_dropdown: true,
        show_search: true,
        option_type: 'manual',
        default_value: { formula: '"value-1"' },
        options,
        ...values,
      })

    const search = async (wrapper, query) => {
      const input = wrapper.get('.select__search-input')
      await input.setValue(query)
      await input.trigger('keyup')
    }

    const visibleOptionNames = (wrapper) =>
      wrapper
        .findAll('.ab-dropdownitem__item:not(.hidden)')
        .map((item) => item.get('.ab-dropdownitem__item-name-text').text())

    test.each([
      [false, false],
      [true, false],
      [false, undefined],
      [true, undefined],
    ])(
      'has no search input for multiple=%s and show_search=%s',
      async (multiple, showSearch) => {
        const wrapper = await mountSearchableChoice({
          multiple,
          show_search: showSearch,
        })

        await wrapper.get('.ab-dropdown__selected').trigger('click')

        expect(wrapper.find('.select__search-input').exists()).toBe(false)
        expect(visibleOptionNames(wrapper)).toEqual(
          options.map(({ name }) => name)
        )
      }
    )

    test.each(['manual', 'formulas'])(
      'filters %s options using case-insensitive substrings without changing the selection',
      async (optionType) => {
        const wrapper = await mountSearchableChoice({
          option_type: optionType,
          formula_name: {
            formula: 'split("Alpha Supplier|Beta Supplier|Gamma Partner", "|")',
          },
          formula_value: { formula: 'split("value-1|value-2|value-3", "|")' },
        })
        const dropdown = wrapper.findComponent({ name: 'ABDropdown' })

        await wrapper.get('.ab-dropdown__selected').trigger('click')
        await search(wrapper, 'TA supp')

        expect(visibleOptionNames(wrapper)).toEqual(['Beta Supplier'])
        expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
          'Alpha Supplier'
        )
        expect(dropdown.emitted('update:modelValue')).toBeUndefined()

        await wrapper
          .get('.ab-dropdownitem__item:not(.hidden) a')
          .trigger('click')

        expect(dropdown.emitted('update:modelValue')).toEqual([['value-2']])
        expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
          'Beta Supplier'
        )
      }
    )

    test('shows the empty state when nothing matches and restores options when cleared', async () => {
      const wrapper = await mountSearchableChoice()

      await wrapper.get('.ab-dropdown__selected').trigger('click')
      await search(wrapper, 'no matching supplier')

      expect(visibleOptionNames(wrapper)).toEqual([])
      expect(wrapper.get('.select__items').element.style.display).toBe('none')
      expect(wrapper.get('.select__items--empty').text()).toBe('dropdown.empty')

      await search(wrapper, '')

      expect(wrapper.find('.select__items--empty').exists()).toBe(false)
      expect(visibleOptionNames(wrapper)).toEqual(
        options.map(({ name }) => name)
      )
    })

    test('clears the query when closed and reopened', async () => {
      const wrapper = await mountSearchableChoice()

      await wrapper.get('.ab-dropdown__selected').trigger('click')
      await search(wrapper, 'beta')
      await wrapper.get('.ab-dropdown').trigger('focusout', {
        relatedTarget: document.createElement('button'),
      })

      expect(wrapper.get('.ab-dropdown__items').classes()).toContain('hidden')

      await wrapper.get('.ab-dropdown__selected').trigger('click')

      expect(wrapper.get('.select__search-input').element.value).toBe('')
      expect(visibleOptionNames(wrapper)).toEqual(
        options.map(({ name }) => name)
      )
      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
        'Alpha Supplier'
      )
    })

    test.each(['manual', 'formulas'])(
      'retains multiple %s selections across searches and reopening',
      async (optionType) => {
        const wrapper = await mountSearchableChoice({
          multiple: true,
          option_type: optionType,
          default_value: { formula: 'split("value-1|value-3", "|")' },
          formula_name: {
            formula: 'split("Alpha Supplier|Beta Supplier|Gamma Partner", "|")',
          },
          formula_value: { formula: 'split("value-1|value-2|value-3", "|")' },
        })
        const dropdown = wrapper.findComponent({ name: 'ABDropdown' })

        await wrapper.get('.ab-dropdown__selected').trigger('click')
        await search(wrapper, 'BETA')

        expect(visibleOptionNames(wrapper)).toEqual(['Beta Supplier'])
        expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
          'Alpha Supplier, Gamma Partner'
        )
        expect(dropdown.emitted('update:modelValue')).toBeUndefined()

        await wrapper
          .get('.ab-dropdownitem__item:not(.hidden) a')
          .trigger('click')

        expect(dropdown.emitted('update:modelValue')).toEqual([
          [['value-1', 'value-3', 'value-2']],
        ])
        expect(wrapper.get('.ab-dropdown__items').classes()).not.toContain(
          'hidden'
        )

        await search(wrapper, 'ALPHA')

        expect(visibleOptionNames(wrapper)).toEqual(['Alpha Supplier'])
        expect(
          wrapper.get('.ab-dropdownitem__item:not(.hidden)').classes()
        ).toContain('active')

        await wrapper.get('.ab-dropdown').trigger('focusout', {
          relatedTarget: document.createElement('button'),
        })
        await wrapper.get('.ab-dropdown__selected').trigger('click')

        expect(wrapper.get('.select__search-input').element.value).toBe('')
        expect(wrapper.findAll('.ab-dropdownitem__item.active')).toHaveLength(3)
        expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
          'Alpha Supplier, Gamma Partner, Beta Supplier'
        )
      }
    )

    test('selects a filtered option with the keyboard and closes on Escape', async () => {
      const wrapper = await mountSearchableChoice()
      const body = new DOMWrapper(document.body)
      const dropdown = wrapper.findComponent({ name: 'ABDropdown' })

      await wrapper.get('.ab-dropdown').trigger('focusin')
      await search(wrapper, 'beta')
      await body.trigger('keydown', { key: 'ArrowDown' })

      expect(
        wrapper.get('.ab-dropdownitem__item:not(.hidden)').classes()
      ).toContain('hover')

      await body.trigger('keydown', { key: 'Enter' })

      expect(dropdown.emitted('update:modelValue')).toEqual([['value-2']])
      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
        'Beta Supplier'
      )
      expect(wrapper.get('.ab-dropdown__items').classes()).toContain('hidden')

      await wrapper.get('.ab-dropdown__selected').trigger('click')
      await search(wrapper, 'gamma')
      await body.trigger('keydown', { key: 'Escape' })

      expect(wrapper.get('.ab-dropdown__items').classes()).toContain('hidden')
      expect(wrapper.get('.select__search-input').element.value).toBe('')
      expect(wrapper.get('.ab-dropdown__selected-text').text()).toBe(
        'Beta Supplier'
      )
      expect(dropdown.emitted('update:modelValue')).toHaveLength(1)
    })
  })
})
