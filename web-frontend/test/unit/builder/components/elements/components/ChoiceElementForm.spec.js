import { mountSuspended } from '@nuxt/test-utils/runtime'
import ChoiceElementForm from '@baserow/modules/builder/components/elements/components/forms/general/ChoiceElementForm.vue'

describe('ChoiceElementForm', () => {
  let wrapper

  afterEach(() => {
    wrapper?.unmount()
  })

  const mountComponent = async (defaultValues = {}) => {
    wrapper = await mountSuspended(ChoiceElementForm, {
      props: { defaultValues },
      global: {
        provide: {
          workspace: {},
          builder: { theme: {} },
          currentPage: { elements: [] },
          elementPage: { elements: [] },
          mode: 'editing',
        },
        stubs: {
          InjectedFormulaInput: true,
          CustomStyleButton: true,
        },
      },
    })
    return wrapper
  }

  const searchCheckbox = (wrapper) =>
    wrapper
      .findAll('.checkbox')
      .find((checkbox) => checkbox.text() === 'choiceElementForm.enableSearch')

  const selectDisplay = (wrapper, label) =>
    wrapper
      .findAll('.radio-group__radio-button')
      .find((button) => button.text() === label)
      .trigger('click')

  const lastValuesChanged = (wrapper) =>
    wrapper.emitted('values-changed').at(-1)[0]

  test('defaults to disabled and includes search in emitted values', async () => {
    const wrapper = await mountComponent()
    const checkbox = searchCheckbox(wrapper).get('input[type="checkbox"]')

    expect(checkbox.element.checked).toBe(false)

    await checkbox.setValue(true)

    expect(lastValuesChanged(wrapper).show_search).toBe(true)

    await checkbox.setValue(false)

    expect(lastValuesChanged(wrapper).show_search).toBe(false)
  })

  test('loads the saved search setting', async () => {
    const wrapper = await mountComponent({ show_search: true })

    expect(
      searchCheckbox(wrapper).get('input[type="checkbox"]').element.checked
    ).toBe(true)
  })

  test.each([
    [false, 'choiceElementForm.radio'],
    [true, 'choiceElementForm.checkbox'],
  ])(
    'only shows search for dropdowns and preserves its value for multiple=%s',
    async (multiple, alternativeDisplay) => {
      const wrapper = await mountComponent({ multiple, show_search: true })

      await selectDisplay(wrapper, alternativeDisplay)

      expect(searchCheckbox(wrapper)).toBeUndefined()
      expect(lastValuesChanged(wrapper)).toMatchObject({
        show_as_dropdown: false,
        show_search: true,
      })

      await selectDisplay(wrapper, 'choiceElementForm.dropdown')

      expect(
        searchCheckbox(wrapper).get('input[type="checkbox"]').element.checked
      ).toBe(true)
      expect(lastValuesChanged(wrapper)).toMatchObject({
        show_as_dropdown: true,
        show_search: true,
      })
    }
  )

  test('hides search for an initially non-dropdown choice', async () => {
    const wrapper = await mountComponent({ show_as_dropdown: false })

    expect(searchCheckbox(wrapper)).toBeUndefined()

    await selectDisplay(wrapper, 'choiceElementForm.dropdown')

    expect(
      searchCheckbox(wrapper).get('input[type="checkbox"]').element.checked
    ).toBe(false)
  })
})
