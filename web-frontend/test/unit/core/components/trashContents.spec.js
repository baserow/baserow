import { shallowMount } from '@vue/test-utils'
import TrashContents from '@baserow/modules/core/components/trash/TrashContents'

describe('TrashContents', () => {
  const workspace = { id: 1, name: 'Workspace', trashed: false }
  const application = { id: 10, name: 'Database', trashed: false }

  const mountContents = ({
    storeWorkspace = { id: 1, _: { permissionsLoaded: true } },
    hasPermission = () => false,
    props = {},
  } = {}) => {
    return shallowMount(TrashContents, {
      props: {
        selectedTrashWorkspace: workspace,
        trashContents: [],
        loadingContents: false,
        loadingNextPage: false,
        totalServerSideTrashContentsCount: 1,
        ...props,
      },
      global: {
        stubs: { InfiniteScroll: true, TrashEmptyModal: true },
        mocks: {
          $t: (key) => key,
          $config: { public: { hoursUntilTrashPermanentlyDeleted: 72 } },
          $store: {
            getters: { 'workspace/get': () => storeWorkspace },
          },
          $hasPermission: hasPermission,
        },
      },
    })
  }

  it('hides the workspace empty button without workspace.empty_trash', () => {
    const hasPermission = vi.fn(() => false)
    const wrapper = mountContents({ hasPermission })

    expect(wrapper.vm.canEmpty).toBe(false)
    expect(hasPermission).toHaveBeenCalledWith(
      'workspace.empty_trash',
      expect.objectContaining({ id: 1 }),
      1
    )
  })

  it('shows the workspace empty button with workspace.empty_trash', () => {
    const wrapper = mountContents({ hasPermission: () => true })

    expect(wrapper.vm.canEmpty).toBe(true)
  })

  it('shows the empty button when the workspace permissions are unknown', () => {
    const hasPermission = vi.fn(() => false)
    const wrapper = mountContents({ storeWorkspace: null, hasPermission })

    expect(wrapper.vm.canEmpty).toBe(true)
    expect(hasPermission).not.toHaveBeenCalled()
  })

  it('keeps the application empty button for members', () => {
    const wrapper = mountContents({
      props: { selectedTrashApplication: application },
    })

    expect(wrapper.vm.canEmpty).toBe(true)
  })
})
