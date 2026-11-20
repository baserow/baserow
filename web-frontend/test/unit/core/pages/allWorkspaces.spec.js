import flushPromises from 'flush-promises'
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

  test('opens the linked template in the Templates modal', async () => {
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    testApp.mock.onGet('/settings/').reply(200, {})
    testApp.mock.onGet('/workspaces/').reply(200, [])
    testApp.mock.onGet('/applications/').reply(200, [])
    testApp.mock.onGet(/\/jobs\//).reply(200, { jobs: [] })
    const show = vi.fn()
    await testApp.mount(AllWorkspaces, {
      route: '/all-workspaces?template=sprint-tracker',
      global: {
        stubs: {
          TemplateModal: { template: '<div />', methods: { show } },
        },
      },
    })
    await flushPromises()

    expect(show).toHaveBeenCalledWith('sprint-tracker')
    await vi.waitFor(() =>
      expect(useRouter().currentRoute.value.query).toStrictEqual({})
    )
  })
})
