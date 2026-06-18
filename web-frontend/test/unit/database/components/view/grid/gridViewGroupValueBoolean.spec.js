import { TestApp } from '@baserow/test/helpers/testApp'
import { BooleanFieldType } from '@baserow/modules/database/fieldTypes'
import GridViewGroupValueBoolean from '@baserow/modules/database/components/view/grid/GridViewGroupValueBoolean'

describe('GridViewGroupValueBoolean component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (value) => {
    return testApp.mount(GridViewGroupValueBoolean, {
      props: { value },
    })
  }

  test('renders true as a check icon', async () => {
    const wrapper = await mountComponent(true)

    expect(wrapper.classes()).toContain('grid-view__group-value-boolean--true')
    expect(wrapper.find('.iconoir-check').exists()).toBe(true)
    expect(wrapper.find('.iconoir-cancel').exists()).toBe(false)
  })

  test('renders false as a cancel icon', async () => {
    const wrapper = await mountComponent(false)

    expect(wrapper.classes()).toContain('grid-view__group-value-boolean--false')
    expect(wrapper.find('.iconoir-cancel').exists()).toBe(true)
    expect(wrapper.find('.iconoir-check').exists()).toBe(false)
  })

  test('is used by boolean group-by values', () => {
    expect(new BooleanFieldType().getGroupByComponent()).toBe(
      GridViewGroupValueBoolean
    )
  })
})
