import { TestApp } from '@baserow/test/helpers/testApp'
import FunctionalFormulaURLArrayItem from '@baserow/modules/database/components/formula/array/FunctionalFormulaURLArrayItem.vue'

describe('GridViewFieldLookup component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (props, slots = {}) => {
    return testApp.mount(FunctionalFormulaURLArrayItem, {
      props,
      slots,
    })
  }

  const field = {
    id: 5326,
    table_id: 563,
    name: 'Lookup',
    order: 4,
    type: 'lookup',
    primary: false,
    read_only: true,
    description: null,
    duration_format: null,
    date_force_timezone: null,
    date_format: null,
    date_time_format: null,
    date_include_time: null,
    date_show_tzinfo: null,
    array_formula_type: 'url',
    error: null,
    nullable: true,
    number_decimal_places: null,
    through_field_id: 5323,
    through_field_name: 'secondary',
    target_field_id: 5322,
    target_field_name: 'URL',
    formula_type: 'array',
    _: {
      type: {
        type: 'lookup',
        iconClass: 'iconoir-binocular',
        name: 'Lookup',
        isReadOnly: true,
        canImport: false,
      },
      loading: false,
    },
  }

  test('URL lookup field shows text when inactive', async () => {
    const wrapper = await mountComponent({
      field,
      readOnly: false,
      selected: false,
      storePrefix: 'page/',
      value: 'baserow.io',
      workspaceId: 10,
    })

    expect(wrapper.element).toMatchSnapshot()
  })

  test('URL lookup field shows hyperlink when active', async () => {
    const wrapper = await mountComponent({
      field,
      readOnly: false,
      selected: true,
      storePrefix: 'page/',
      value: 'baserow.io',
      workspaceId: 10,
    })

    expect(wrapper.element).toMatchSnapshot()
  })
})
