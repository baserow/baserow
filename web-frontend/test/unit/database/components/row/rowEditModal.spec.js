import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import Modal from '@baserow/modules/core/components/Modal'

describe('RowEditModal', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const database = { id: 1, workspace: { id: 1 } }
  const table = { id: 1 }
  const view = { id: 1, ownership_type: 'collaborative' }
  const row = { id: 1, _: {} }

  const openModal = async () => {
    const wrapper = await testApp.mount(RowEditModal, {
      props: {
        database,
        table,
        view,
        allFieldsInTable: [],
        visibleFields: [],
        rows: [row],
        readOnly: true,
      },
      global: {
        stubs: { RowEditModalFieldsList: true, RowEditModalSidebar: true },
      },
    })
    wrapper.vm.show(row.id)
    await flushPromises()
    return wrapper
  }

  test('closes when the backend hides its row', async () => {
    const wrapper = await openModal()

    await testApp.store.dispatch('rowModal/rowsHiddenByBackend', {
      tableId: table.id,
      rowIds: [row.id],
    })
    await flushPromises()

    expect(wrapper.emitted('hidden')).toEqual([[{ row }]])
  })

  test('closes the modals opened on top of it first when the backend hides its row', async () => {
    const wrapper = await openModal()
    const rootModal = wrapper.vm.getRootModal()
    const openChildModal = async (parentModal) => {
      const child = await testApp.mount(Modal, {
        global: {
          provide: {
            registerChild: parentModal.registerChild,
            unregisterChild: parentModal.unregisterChild,
          },
        },
      })
      child.vm.show()
      return child
    }
    const child = await openChildModal(rootModal)
    const grandchild = await openChildModal(child.vm)
    // A modal only flips `open` after a timeout, so the closes cascade over timers.
    const waitForModalsToClose = async () => {
      for (let i = 0; i < 3; i++) {
        await new Promise((resolve) => setTimeout(resolve))
        await flushPromises()
      }
    }

    await testApp.store.dispatch('rowModal/rowsHiddenByBackend', {
      tableId: table.id,
      rowIds: [row.id],
    })
    await waitForModalsToClose()

    expect(grandchild.emitted('hidden')).toEqual([[]])
    expect(child.emitted('hidden')).toEqual([[]])
    expect(wrapper.emitted('hidden')).toEqual([[{ row }]])
  })

  test('stays open when another row is hidden', async () => {
    const wrapper = await openModal()

    await testApp.store.dispatch('rowModal/rowsHiddenByBackend', {
      tableId: table.id,
      rowIds: [2],
    })
    await flushPromises()

    expect(wrapper.emitted('hidden')).toBeUndefined()
  })

  test('stays open when its row leaves the view buffer', async () => {
    const wrapper = await openModal()

    await wrapper.setProps({ rows: [] })
    await flushPromises()

    expect(wrapper.emitted('hidden')).toBeUndefined()
  })
})
