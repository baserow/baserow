import { TestApp } from '@baserow/test/helpers/testApp'
import { MultipleSelectFieldType } from '@baserow/modules/database/fieldTypes'
import GridViewGroupValueMultipleSelect from '@baserow/modules/database/components/view/grid/GridViewGroupValueMultipleSelect'

describe('GridViewGroupValueMultipleSelect component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('renders a chip for each select option value', async () => {
    const wrapper = await testApp.mount(GridViewGroupValueMultipleSelect, {
      props: {
        value: [
          { id: 1, value: 'Red', color: 'red' },
          { id: 2, value: 'Blue', color: 'blue' },
        ],
      },
    })

    expect(wrapper.text()).toContain('Red')
    expect(wrapper.text()).toContain('Blue')
  })

  test('is used by multiple select group-by values', () => {
    expect(new MultipleSelectFieldType().getGroupByComponent()).toBe(
      GridViewGroupValueMultipleSelect
    )
  })
})
