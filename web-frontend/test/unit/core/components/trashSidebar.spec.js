import { shallowMount } from '@vue/test-utils'
import TrashSidebar from '@baserow/modules/core/components/trash/TrashSidebar'

describe('TrashSidebar', () => {
  const workspaceA = { id: 1, name: 'Workspace A', applications: [] }
  const workspaceB = { id: 2, name: 'Workspace B', applications: [] }
  const application = { id: 10, name: 'Database', type: 'database' }

  const mountSidebar = (props) => {
    return shallowMount(TrashSidebar, {
      props: {
        workspaces: [workspaceA, workspaceB],
        ...props,
      },
      global: {
        stubs: { Dropdown: true, DropdownItem: true },
        mocks: {
          $registry: { getAll: () => ({}) },
        },
      },
    })
  }

  it('emits when another workspace is chosen', async () => {
    const wrapper = mountSidebar({ selectedTrashWorkspace: workspaceA })

    wrapper.vm.emitIfNotAlreadySelectedTrashWorkspace(workspaceB)

    expect(wrapper.emitted('selected')).toEqual([[{ workspace: workspaceB }]])
  })

  it('emits when another workspace is chosen while an application is selected', async () => {
    const wrapper = mountSidebar({
      selectedTrashWorkspace: workspaceA,
      selectedTrashApplication: application,
    })

    wrapper.vm.emitIfNotAlreadySelectedTrashWorkspace(workspaceB)

    expect(wrapper.emitted('selected')).toEqual([[{ workspace: workspaceB }]])
  })

  it('emits when the same workspace is chosen while an application is selected', async () => {
    const wrapper = mountSidebar({
      selectedTrashWorkspace: workspaceA,
      selectedTrashApplication: application,
    })

    wrapper.vm.emitIfNotAlreadySelectedTrashWorkspace(workspaceA)

    expect(wrapper.emitted('selected')).toEqual([[{ workspace: workspaceA }]])
  })

  it('does not emit when the already selected workspace is chosen again', async () => {
    const wrapper = mountSidebar({ selectedTrashWorkspace: workspaceA })

    wrapper.vm.emitIfNotAlreadySelectedTrashWorkspace(workspaceA)

    expect(wrapper.emitted('selected')).toBeUndefined()
  })
})
