import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import SnapshotsModal from '@baserow/modules/core/components/snapshots/SnapshotsModal'

describe('SnapshotsModal', () => {
  let testApp = null
  const application = {
    id: 7,
    name: 'CRM',
    type: 'database',
    workspace: { id: 3, name: 'Acme' },
  }
  const listUrl = `/snapshots/application/${application.id}/`
  const usageUrl = `/snapshots/application/${application.id}/usage/`
  const keepUrl = `/snapshots/application/${application.id}/keep/`

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const snapshot = (id, day, isProtected = false) => ({
    id,
    name: `S${id}`,
    snapshot_from_application: application.id,
    created_at: `2026-11-0${day}T10:00:00Z`,
    created_by: { username: 'staff-dev' },
    created_automatically: false,
    protected: isProtected,
  })

  const usage = (values = {}) => ({
    used: 3,
    limit: 10,
    over_allowance: false,
    blocked: false,
    can_exceed_allowance: false,
    snapshot_count: 3,
    default_keep: 0,
    max_keep: null,
    expiration_days: 360,
    keep: 3,
    effective_keep: 3,
    application_snapshot_count: 3,
    protected_count: 0,
    ...values,
  })

  const mountModal = async (snapshots, usageValues = {}) => {
    testApp.mock.onGet(listUrl).reply(200, snapshots)
    testApp.mock.onGet(usageUrl).reply(200, usage(usageValues))
    const wrapper = await testApp.mount(SnapshotsModal, {
      props: { application },
    })
    wrapper.vm.show()
    await flushPromises()
    return wrapper
  }

  // The test translations add the parameters after the key.
  const findButton = (wrapper, key) =>
    wrapper
      .findAll('button')
      .find((button) => button.text().split(' - ')[0] === key)

  test('takes a snapshot and raises the keep when it keeps none', async () => {
    const wrapper = await mountModal([], {
      keep: null,
      effective_keep: 0,
      used: 0,
    })

    expect(wrapper.vm.blockedReason).toBe('none')
    expect(wrapper.text()).toContain('snapshotsModal.keepsNoneTitle')
    expect(wrapper.text()).toContain('snapshotsModal.keepsNoneRaise')
    expect(findButton(wrapper, 'snapshotsModal.raiseAndCreate')).toBeTruthy()

    testApp.mock.onPost(listUrl).reply(202, {
      id: 1,
      type: 'create_snapshot',
      state: 'pending',
      progress_percentage: 0,
      snapshot: snapshot(1, 1, true),
    })
    wrapper.vm.submitted({ name: 'New' })
    await flushPromises()

    expect(testApp.mock.history.post).toHaveLength(1)
    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      name: 'New',
      raise_keep: true,
    })
  })

  test('offers to raise the keep when every kept snapshot is protected', async () => {
    const wrapper = await mountModal(
      [snapshot(2, 2, true), snapshot(1, 1, true)],
      { keep: 2, effective_keep: 2, protected_count: 2 }
    )

    expect(wrapper.vm.blockedReason).toBe('protected')
    expect(wrapper.text()).toContain('snapshotsModal.allProtectedTitle')
    expect(wrapper.text()).toContain('snapshotsModal.allProtectedRaise')
    expect(wrapper.vm.raisedKeep).toBe(3)
    expect(findButton(wrapper, 'snapshotsModal.raiseAndCreate')).toBeTruthy()
    expect(wrapper.text()).not.toContain('snapshotKeep.overAllowance')
  })

  test('warns when raising the keep goes over the allowance', async () => {
    const wrapper = await mountModal([snapshot(1, 1, true)], {
      keep: 1,
      effective_keep: 1,
      protected_count: 1,
      used: 10,
      can_exceed_allowance: true,
    })

    expect(findButton(wrapper, 'snapshotsModal.raiseAndCreate')).toBeTruthy()
    expect(wrapper.text()).toContain('snapshotKeep.overAllowance')
  })

  test('says why the keep can not be raised', async () => {
    const full = await mountModal([snapshot(1, 1, true)], {
      keep: 1,
      effective_keep: 1,
      protected_count: 1,
      used: 10,
    })
    expect(findButton(full, 'snapshotsModal.raiseAndCreate')).toBeFalsy()
    expect(full.text()).toContain('snapshotsModal.allProtectedCantRaise')
    expect(full.text()).toContain('snapshotsModal.cantRaiseAllowance')

    const atMaximum = await mountModal([snapshot(1, 1, true)], {
      keep: 1,
      effective_keep: 1,
      protected_count: 1,
      max_keep: 1,
    })
    expect(findButton(atMaximum, 'snapshotsModal.raiseAndCreate')).toBeFalsy()
    expect(atMaximum.text()).toContain('snapshotsModal.cantRaiseAboveMaximum')
  })

  test('says snapshots are turned off without offering a keep', async () => {
    const wrapper = await mountModal([], { limit: 0 })

    expect(wrapper.vm.blockedReason).toBe('disabled')
    expect(findButton(wrapper, 'snapshotsModal.raiseAndCreate')).toBeFalsy()
    expect(wrapper.text()).toContain('snapshotsModal.usageDisabled')
  })

  test('says snapshots are paused when the workspace is blocked', async () => {
    const wrapper = await mountModal([], {
      blocked: true,
      over_allowance: true,
    })

    expect(wrapper.vm.blockedReason).toBe('blocked')
    expect(wrapper.text()).toContain('snapshotsModal.blockedTitle')
    expect(findButton(wrapper, 'snapshotsModal.raiseAndCreate')).toBeFalsy()
  })

  test('asks before a new snapshot replaces the oldest unprotected one', async () => {
    const wrapper = await mountModal([
      snapshot(3, 3),
      snapshot(2, 2, true),
      snapshot(1, 1),
    ])

    expect(wrapper.vm.snapshotToReplace.id).toBe(1)
    wrapper.vm.submitted({ name: 'New' })
    await flushPromises()

    expect(wrapper.vm.confirmingReplace).toBe(true)
    expect(wrapper.text()).toContain('snapshotsModal.confirmReplace')
    expect(testApp.mock.history.post).toHaveLength(0)

    await findButton(wrapper, 'action.cancel').trigger('click')
    expect(wrapper.vm.confirmingReplace).toBe(false)
    expect(testApp.mock.history.post).toHaveLength(0)
  })

  test('loads the snapshots again after a keep change', async () => {
    const wrapper = await mountModal([
      snapshot(3, 3),
      snapshot(2, 2),
      snapshot(1, 1),
    ])
    // Lowering the keep to 1 deleted S1 and S2.
    testApp.mock.onGet(listUrl).reply(200, [snapshot(3, 3)])
    testApp.mock
      .onPatch(keepUrl)
      .reply(200, usage({ keep: 1, effective_keep: 1 }))
    testApp.mock
      .onGet(usageUrl)
      .reply(200, usage({ keep: 1, effective_keep: 1, used: 1 }))

    wrapper.vm.keepUpdated(usage({ keep: 1, effective_keep: 1 }))
    await flushPromises()

    expect(wrapper.vm.snapshots.map(({ id }) => id)).toEqual([3])
    // So the next snapshot replaces the one that's really there.
    expect(wrapper.vm.snapshotToReplace.id).toBe(3)
  })
})
