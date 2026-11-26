import flushPromises from 'flush-promises'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { TestApp } from '@baserow/test/helpers/testApp'
import AllWorkspaces from '@baserow/modules/core/pages/allWorkspaces'
import AllWorkspacesHeader from '@baserow/modules/core/components/allWorkspaces/AllWorkspacesHeader'
import { CORE_ACTION_SCOPES } from '@baserow/modules/core/utils/undoRedoConstants'

const { flags } = vi.hoisted(() => ({ flags: { userTemplatesOff: false } }))
mockNuxtImport('useNuxtApp', (original) => () => {
  const nuxtApp = original()
  if (!flags.userTemplatesOff) {
    return nuxtApp
  }
  return new Proxy(nuxtApp, {
    get: (target, property, receiver) =>
      property === '$featureFlagIsEnabled'
        ? () => false
        : Reflect.get(target, property, receiver),
  })
})

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
    flags.userTemplatesOff = false
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

  const mountLinked = async (route) => {
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    testApp.mock.onGet('/settings/').reply(200, {})
    testApp.mock.onGet('/workspaces/').reply(200, [])
    testApp.mock.onGet('/applications/').reply(200, [])
    testApp.mock.onGet(/\/jobs\//).reply(200, { jobs: [] })
    const methods = { show: vi.fn(), showOwn: vi.fn() }
    const wrapper = await testApp.mount(AllWorkspaces, {
      route,
      global: {
        stubs: {
          TemplateModal: { template: '<div class="modal" />', methods },
        },
      },
    })
    await flushPromises()
    return { wrapper, methods }
  }

  test.each([
    [
      'the linked template',
      '?template=sprint-tracker',
      [['sprint-tracker']],
      [],
    ],
    ['your templates', '?templates=own', [], [[]]],
  ])(
    'opens %s in the Templates modal',
    async (_name, query, showCalls, showOwnCalls) => {
      const { methods } = await mountLinked(`/all-workspaces${query}`)

      expect(methods.show.mock.calls).toStrictEqual(showCalls)
      expect(methods.showOwn.mock.calls).toStrictEqual(showOwnCalls)
      await vi.waitFor(() =>
        expect(useRouter().currentRoute.value.query).toStrictEqual({})
      )
    }
  )

  test('opens no Templates modal from a link without user templates', async () => {
    flags.userTemplatesOff = true

    const { wrapper } = await mountLinked('/all-workspaces?templates=own')

    expect(wrapper.find('.modal').exists()).toBe(false)
  })
})
