import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import SnapshotKeep from '@baserow/modules/core/components/snapshots/SnapshotKeep'

describe('SnapshotKeep', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const usage = (values = {}) => ({
    used: 4,
    limit: 5,
    over_allowance: false,
    snapshot_count: 2,
    default_keep: 2,
    max_keep: null,
    expiration_days: 360,
    keep: null,
    effective_keep: 2,
    application_snapshot_count: 2,
    protected_count: 0,
    ...values,
  })

  const snapshots = [
    {
      id: 2,
      name: 'Newest',
      created_at: '2026-11-02T10:00:00Z',
      protected: false,
    },
    {
      id: 1,
      name: 'Oldest',
      created_at: '2026-11-01T10:00:00Z',
      protected: false,
    },
  ]

  const mountComponent = (values = {}) =>
    testApp.mount(SnapshotKeep, {
      props: {
        application: { id: 7, name: 'CRM' },
        usage: usage(values),
        snapshots,
        canUpdate: true,
      },
    })

  const findButton = (wrapper, text) =>
    wrapper.findAll('button').find((button) => button.text() === text)

  test('says the keep comes from the workspace default', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.find('.snapshot-keep__value').text()).toBe('2')
    expect(wrapper.text()).toContain('snapshotKeep.descriptionDefault')
  })

  test('shows a validation error instead of going past the allowance', async () => {
    const wrapper = await mountComponent()

    await wrapper.vm.edit(4)
    await flushPromises()

    // Up to 3: what's left of the allowance on top of its keep of 2.
    expect(wrapper.find('.snapshot-keep__error').text()).toBe(
      'snapshotKeep.errorExceedsAllowance - 3'
    )
    expect(testApp.mock.history.patch).toHaveLength(0)
  })

  test('warns when the keep can go past the allowance', async () => {
    testApp.mock
      .onPatch('/snapshots/application/7/keep/')
      .reply(200, usage({ keep: 4, effective_keep: 4, used: 6 }))
    const wrapper = await mountComponent({ can_exceed_allowance: true })

    await wrapper.vm.edit(4)
    await flushPromises()

    expect(wrapper.find('.snapshot-keep__error').exists()).toBe(false)
    expect(wrapper.find('.snapshot-keep__warning').text()).toContain(
      'snapshotKeep.overAllowance'
    )
    // The maximum keep is the only limit left, and there's none.
    expect(wrapper.find('.snapshot-keep__hint').exists()).toBe(false)

    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      keep: 4,
      delete_snapshots: false,
    })
  })

  test('saves a keep within the allowance', async () => {
    testApp.mock
      .onPatch('/snapshots/application/7/keep/')
      .reply(200, usage({ keep: 3, effective_keep: 3, used: 5 }))
    const wrapper = await mountComponent()

    await wrapper.vm.edit(3)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      keep: 3,
      delete_snapshots: false,
    })
    expect(wrapper.emitted('updated')[0][0].effective_keep).toBe(3)
  })

  test('asks before a lower keep deletes snapshots', async () => {
    testApp.mock
      .onPatch('/snapshots/application/7/keep/')
      .reply(200, usage({ keep: 1, effective_keep: 1, used: 3 }))
    const wrapper = await mountComponent()

    await wrapper.vm.edit(1)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('.snapshot-keep__confirm').text()).toContain(
      'snapshotKeep.confirmDelete'
    )
    expect(testApp.mock.history.patch).toHaveLength(0)

    await findButton(wrapper, 'snapshotKeep.deleteAndSave').trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      keep: 1,
      delete_snapshots: true,
    })
  })
})

describe('SnapshotKeep with an out of date list', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('asks to confirm when the server says snapshots would be deleted', async () => {
    testApp.mock.onPatch('/snapshots/application/7/keep/').reply(400, {
      error: 'ERROR_SNAPSHOT_KEEP_CHANGE_DELETES_SNAPSHOTS',
      detail:
        'Lowering the keep deletes 2 snapshot(s). Send `delete_snapshots`.',
    })
    const wrapper = await testApp.mount(SnapshotKeep, {
      props: {
        application: { id: 7, name: 'CRM' },
        usage: {
          used: 3,
          limit: 10,
          over_allowance: false,
          blocked: false,
          snapshot_count: 0,
          default_keep: 0,
          max_keep: null,
          expiration_days: 360,
          keep: 3,
          effective_keep: 3,
          application_snapshot_count: 0,
          protected_count: 0,
        },
        // The list doesn't know about the snapshots that were added since.
        snapshots: [],
        canUpdate: true,
      },
    })

    await wrapper.vm.edit(1)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.emitted('stale')).toHaveLength(1)
    expect(wrapper.find('.snapshot-keep__confirm').text()).toContain(
      'snapshotKeep.confirmDelete'
    )
  })
})
