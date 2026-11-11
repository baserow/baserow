import { TestApp } from '@baserow/test/helpers/testApp'
import AllWorkspaces from '@baserow/modules/core/pages/allWorkspaces'
import AllWorkspacesHeader from '@baserow/modules/core/components/allWorkspaces/AllWorkspacesHeader'
import { CORE_ACTION_SCOPES } from '@baserow/modules/core/utils/undoRedoConstants'

describe('All workspaces page', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
    testApp.authenticate({ id: 1, preferences: {} })
    testApp.mock
      .onGet('/user/dashboard/')
      .reply(200, { workspace_invitations: [] })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('undoes actions of every workspace only while it is shown', async () => {
    testApp.store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      CORE_ACTION_SCOPES.allWorkspaces(false)
    )

    const wrapper = await testApp.mount(AllWorkspaces)
    expect(
      testApp.store.getters['undoRedo/getCurrentScope'].all_workspaces
    ).toBe(true)

    wrapper.unmount()
    expect(
      testApp.store.getters['undoRedo/getCurrentScope'].all_workspaces
    ).toBe(false)
  })

  test('offers only the application types that can be created', async () => {
    vi.spyOn(
      testApp.getRegistry().get('application', 'agent'),
      'canBeCreated'
    ).mockReturnValue(false)

    const wrapper = await testApp.mount(AllWorkspaces)
    const offered = wrapper
      .findComponent(AllWorkspacesHeader)
      .props('applicationTypes')
      .map((applicationType) => applicationType.getType())

    expect(offered).toContain('database')
    expect(offered).not.toContain('agent')
  })
})
