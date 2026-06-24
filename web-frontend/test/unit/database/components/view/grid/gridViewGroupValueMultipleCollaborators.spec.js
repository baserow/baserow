import { TestApp } from '@baserow/test/helpers/testApp'
import { MultipleCollaboratorsFieldType } from '@baserow/modules/database/fieldTypes'
import GridViewGroupValueMultipleCollaborators from '@baserow/modules/database/components/view/grid/GridViewGroupValueMultipleCollaborators'

describe('GridViewGroupValueMultipleCollaborators component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('renders a chip for each collaborator name', async () => {
    const wrapper = await testApp.mount(
      GridViewGroupValueMultipleCollaborators,
      {
        props: {
          value: [
            { id: 1, name: 'Alice' },
            { id: 2, name: 'Bob' },
          ],
        },
      }
    )

    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
  })

  test('is used by collaborator group-by values', () => {
    expect(new MultipleCollaboratorsFieldType().getGroupByComponent()).toBe(
      GridViewGroupValueMultipleCollaborators
    )
  })
})
