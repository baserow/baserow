import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldSingleSelect from '@baserow/modules/database/components/view/grid/fields/GridViewFieldSingleSelect'
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'

describe('GridViewFieldSingleSelect component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const option = { id: 1, value: 'Done', color: 'green' }
  const field = {
    id: 1,
    name: 'Status',
    order: 0,
    type: 'single_select',
    primary: false,
    select_options: [option],
    _: { loading: false },
  }

  const mountComponent = (value, readOnly = true) =>
    testApp.mount(GridViewFieldSingleSelect, {
      props: {
        field,
        value,
        readOnly,
        selected: true,
        storePrefix: 'page/',
        workspaceId: 10,
      },
    })

  test('renders the selected option', async () => {
    const wrapper = await mountComponent(option)

    const selected = wrapper.find('.grid-field-single-select__option')
    expect(selected.text()).toBe('Done')
    expect(selected.classes()).toContain('background-color--green')
  })

  // A row missing the field's key, e.g. one added before the field reached
  // the store, passes an undefined value.
  test.each([[null], [undefined]])(
    'renders no option for the value %s',
    async (value) => {
      const wrapper = await mountComponent(value)

      expect(wrapper.find('.grid-field-single-select__option').exists()).toBe(
        false
      )
    }
  )

  test('saves an option picked for a cell with an undefined value', async () => {
    const wrapper = await mountComponent(undefined, false)

    wrapper.findComponent(FieldSelectOptionsDropdown).vm.$emit('input', 1)

    expect(wrapper.emitted('update')).toEqual([[option, undefined]])
  })
})
