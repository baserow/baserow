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
  const maxSnapshotsUrl = `/snapshots/application/${application.id}/max-snapshots/`

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
    default_max_snapshots: 0,
    max_snapshots_limit: null,
    expiration_days: 360,
    max_snapshots: 3,
    effective_max_snapshots: 3,
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

  test('takes a snapshot and raises the max snapshots when it keeps none', async () => {
    const wrapper = await mountModal([], {
      max_snapshots: null,
      effective_max_snapshots: 0,
      used: 0,
    })

    expect(wrapper.vm.blockedReason).toBe('none')
    expect(wrapper.text()).toContain('snapshotsModal.maxSnapshotsZeroTitle')
    expect(wrapper.text()).toContain('snapshotsModal.maxSnapshotsZeroRaise')
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
      raise_max_snapshots: true,
    })
  })

  test('offers to raise the max snapshots when every kept snapshot is protected', async () => {
    const wrapper = await mountModal(
      [snapshot(2, 2, true), snapshot(1, 1, true)],
      { max_snapshots: 2, effective_max_snapshots: 2, protected_count: 2 }
    )

    expect(wrapper.vm.blockedReason).toBe('protected')
    expect(wrapper.text()).toContain('snapshotsModal.allProtectedTitle')
    expect(wrapper.text()).toContain('snapshotsModal.allProtectedRaise')
    expect(wrapper.vm.raisedMaxSnapshots).toBe(3)
    expect(findButton(wrapper, 'snapshotsModal.raiseAndCreate')).toBeTruthy()
    expect(wrapper.text()).not.toContain('maxSnapshots.overAllowance')
  })

  test('warns when raising the max snapshots goes over the allowance', async () => {
    const wrapper = await mountModal([snapshot(1, 1, true)], {
      max_snapshots: 1,
      effective_max_snapshots: 1,
      protected_count: 1,
      used: 10,
      can_exceed_allowance: true,
    })

    expect(findButton(wrapper, 'snapshotsModal.raiseAndCreate')).toBeTruthy()
    expect(wrapper.text()).toContain('maxSnapshots.overAllowance')
  })

  test('says why the max snapshots can not be raised', async () => {
    const full = await mountModal([snapshot(1, 1, true)], {
      max_snapshots: 1,
      effective_max_snapshots: 1,
      protected_count: 1,
      used: 10,
    })
    expect(findButton(full, 'snapshotsModal.raiseAndCreate')).toBeFalsy()
    expect(full.text()).toContain('snapshotsModal.allProtectedCantRaise')
    expect(full.text()).toContain('snapshotsModal.cantRaiseAllowance')

    const atMaximum = await mountModal([snapshot(1, 1, true)], {
      max_snapshots: 1,
      effective_max_snapshots: 1,
      protected_count: 1,
      max_snapshots_limit: 1,
    })
    expect(findButton(atMaximum, 'snapshotsModal.raiseAndCreate')).toBeFalsy()
    expect(atMaximum.text()).toContain('snapshotsModal.cantRaiseAboveMaximum')
  })

  test('says snapshots are turned off without offering a max', async () => {
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

  test('loads the snapshots again after a max change', async () => {
    const wrapper = await mountModal([
      snapshot(3, 3),
      snapshot(2, 2),
      snapshot(1, 1),
    ])
    // Lowering the max snapshots to 1 deleted S1 and S2.
    testApp.mock.onGet(listUrl).reply(200, [snapshot(3, 3)])
    testApp.mock
      .onPatch(maxSnapshotsUrl)
      .reply(200, usage({ max_snapshots: 1, effective_max_snapshots: 1 }))
    testApp.mock
      .onGet(usageUrl)
      .reply(
        200,
        usage({ max_snapshots: 1, effective_max_snapshots: 1, used: 1 })
      )

    wrapper.vm.maxSnapshotsUpdated(
      usage({ max_snapshots: 1, effective_max_snapshots: 1 })
    )
    await flushPromises()

    expect(wrapper.vm.snapshots.map(({ id }) => id)).toEqual([3])
    // So the next snapshot replaces the one that's really there.
    expect(wrapper.vm.snapshotToReplace.id).toBe(3)
  })

  test('keeps the snapshots listed while they are loaded again', async () => {
    const wrapper = await mountModal([snapshot(2, 2), snapshot(1, 1)])
    let resolveList = null
    testApp.mock.onGet(listUrl).reply(
      () =>
        new Promise((resolve) => {
          resolveList = () => resolve([200, [snapshot(2, 2), snapshot(1, 1)]])
        })
    )

    wrapper.vm.loadSnapshots()
    await flushPromises()

    expect(wrapper.vm.snapshotsLoading).toBe(true)
    expect(wrapper.findAll('.snapshots-modal__rows > *')).toHaveLength(2)
    expect(wrapper.find('.snapshots-modal__loading').exists()).toBe(false)
    resolveList()
    await flushPromises()
  })

  test('loads the snapshots again when they were out of date', async () => {
    const wrapper = await mountModal([snapshot(2, 2), snapshot(1, 1)])
    // Another admin protected S1 in the meantime.
    testApp.mock.onPost(listUrl).reply(400, {
      error: 'ERROR_MAX_SNAPSHOTS_FULL_OF_PROTECTED',
      detail: 'Full.',
    })
    testApp.mock
      .onGet(listUrl)
      .reply(200, [snapshot(2, 2, true), snapshot(1, 1, true)])
    testApp.mock
      .onGet(usageUrl)
      .reply(200, usage({ max_snapshots: 2, effective_max_snapshots: 2 }))
    const listRequests = testApp.mock.history.get.filter(
      ({ url }) => url === listUrl
    ).length

    await wrapper.vm.create({ name: 'New' })
    await flushPromises()

    expect(
      testApp.mock.history.get.filter(({ url }) => url === listUrl)
    ).toHaveLength(listRequests + 1)
    expect(wrapper.vm.blockedReason).toBe('protected')
  })
})
