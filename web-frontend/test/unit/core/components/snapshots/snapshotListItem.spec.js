import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import SnapshotListItem from '@baserow/modules/core/components/snapshots/SnapshotListItem'

describe('SnapshotListItem', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const mountComponent = (snapshot) =>
    testApp.mount(SnapshotListItem, {
      props: {
        snapshot,
        lastUpdated: snapshot.created_at,
        applicationTypeName: 'database',
        expirationDays: 360,
      },
    })

  const snapshot = (values = {}) => ({
    id: 5,
    name: 'Before import cleanup',
    snapshot_from_application: 1,
    created_at: '2026-11-02T10:00:00Z',
    created_by: { username: 'staff-dev' },
    created_automatically: false,
    ...values,
  })

  test('shows who created a manual snapshot and how long it is kept', async () => {
    const wrapper = await mountComponent(snapshot())

    expect(wrapper.find('.snapshots-modal__row-avatar').text()).toBe('S')
    const meta = wrapper.find('.snapshots-modal__row-meta').text()
    expect(meta).toContain('staff-dev')
    expect(meta).toContain('snapshotListItem.keptUntil')
  })

  test('marks automatic snapshots', async () => {
    const wrapper = await mountComponent(
      snapshot({ created_by: null, created_automatically: true })
    )

    expect(
      wrapper
        .find('.snapshots-modal__row-avatar')
        .classes('snapshots-modal__row-avatar--automatic')
    ).toBe(true)
    expect(wrapper.find('.snapshots-modal__row-meta').text()).toContain(
      'snapshotListItem.automatic'
    )
  })

  test('asks for confirmation in the row before deleting', async () => {
    testApp.mock.onDelete('/snapshots/5/').reply(204)
    const wrapper = await mountComponent(snapshot())

    // The "Delete snapshot" item of the row's menu.
    wrapper.vm.showDeleteConfirmation()
    await flushPromises()
    expect(wrapper.text()).toContain('snapshotListItem.confirmDelete')
    expect(testApp.mock.history.delete).toHaveLength(0)

    const deleteButton = wrapper
      .findAll('button')
      .find((button) => button.text() === 'snapshotListItem.deleteConfirm')
    await deleteButton.trigger('click')
    await flushPromises()

    expect(testApp.mock.history.delete).toHaveLength(1)
    expect(wrapper.emitted('snapshot-deleted')[0][0].id).toBe(5)
  })

  test('leaves the list when the snapshot was replaced in the meantime', async () => {
    testApp.mock.onPatch('/snapshots/5/').reply(404, {
      error: 'ERROR_SNAPSHOT_DOES_NOT_EXIST',
      detail: 'The snapshot does not exist.',
    })
    testApp.mock.onDelete('/snapshots/6/').reply(404, {
      error: 'ERROR_SNAPSHOT_DOES_NOT_EXIST',
      detail: 'The snapshot does not exist.',
    })
    const protectedRow = await mountComponent(snapshot({ protected: false }))
    const deletedRow = await mountComponent(snapshot({ id: 6 }))

    await protectedRow.vm.toggleProtected()
    await deletedRow.vm.deleteSnapshot()
    await flushPromises()

    expect(protectedRow.emitted('snapshot-deleted')[0][0].id).toBe(5)
    expect(deletedRow.emitted('snapshot-deleted')[0][0].id).toBe(6)
  })
})
