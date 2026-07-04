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

  test('resolves the name from the store for an optimistic value with only an id', async () => {
    // A newly created group only knows the collaborator id (no name yet); the badge
    // must still render by resolving the name from the workspace store.
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      users: [{ user_id: 5, name: 'Carol' }],
    })

    const wrapper = await testApp.mount(
      GridViewGroupValueMultipleCollaborators,
      {
        props: { value: [{ id: 5 }] },
      }
    )

    expect(wrapper.text()).toContain('Carol')
  })

  test('is used by collaborator group-by values', () => {
    expect(new MultipleCollaboratorsFieldType().getGroupByComponent()).toBe(
      GridViewGroupValueMultipleCollaborators
    )
  })
})
