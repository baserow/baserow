import { TestApp } from '@baserow/test/helpers/testApp'
import FieldButtonSubForm from '@baserow/modules/database/components/field/FieldButtonSubForm'

describe('FieldButtonSubForm', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const mountForm = async (defaultValues = {}) =>
    testApp.mount(FieldButtonSubForm, {
      propsData: {
        table: { id: 1 },
        view: null,
        primary: false,
        allFieldsInTable: [{ id: 1, type: 'text', name: 'Name' }],
        name: 'button',
        database: { id: 1, workspace: { id: 1 } },
        defaultValues,
      },
    })

  test('valid stored formula produces a valid form', async () => {
    const wrapper = await mountForm({
      type: 'button',
      label: 'Open',
      url_formula: { formula: "get('fields.field_1')", mode: 'advanced' },
    })
    expect(wrapper.vm.isFormValid()).toBe(true)
    expect(wrapper.vm.getFormValues().url_formula.formula).toBe(
      "get('fields.field_1')"
    )
  })

  test('a missing label blocks submission', async () => {
    const wrapper = await mountForm({
      type: 'button',
      url_formula: { formula: "get('fields.field_1')", mode: 'advanced' },
    })
    wrapper.vm.v$.$touch()
    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('empty formula blocks submission', async () => {
    const wrapper = await mountForm({
      type: 'button',
      label: 'Open',
      url_formula: { formula: '', mode: 'simple' },
    })
    wrapper.vm.v$.$touch()
    expect(wrapper.vm.isFormValid()).toBe(false)
  })

  test('an invalid formula blocks submission', async () => {
    const wrapper = await mountForm({
      type: 'button',
      label: 'Open',
      url_formula: { formula: "get('fields.field_1')", mode: 'advanced' },
    })
    expect(wrapper.vm.isFormValid()).toBe(true)
    // The formula input only reports parse errors through update:invalid.
    wrapper.vm.urlInvalid = true
    expect(wrapper.vm.isFormValid()).toBe(false)
  })
})
