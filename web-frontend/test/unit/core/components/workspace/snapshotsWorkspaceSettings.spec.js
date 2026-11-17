import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import SnapshotsWorkspaceSettings from '@baserow/modules/core/components/workspace/SnapshotsWorkspaceSettings'

describe('SnapshotsWorkspaceSettings', () => {
  let testApp = null
  const workspace = { id: 12, name: 'Acme' }
  const url = `/snapshots/workspace/${workspace.id}/`

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.commit('application/SET_ITEMS', [
      { id: 1, name: 'CRM', type: 'database', order: 1, workspace },
      { id: 2, name: 'Portal', type: 'builder', order: 2, workspace },
    ])
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const settings = (values = {}) => ({
    used: 5,
    limit: 25,
    over_allowance: false,
    snapshot_count: 4,
    default_keep: 2,
    max_keep: 3,
    expiration_days: 360,
    applications: [
      { id: 1, keep: null, snapshot_count: 2, protected_count: 1 },
      { id: 2, keep: 3, snapshot_count: 2, protected_count: 0 },
    ],
    ...values,
  })

  const mountComponent = async () => {
    const wrapper = await testApp.mount(SnapshotsWorkspaceSettings, {
      props: { workspace },
    })
    await flushPromises()
    return wrapper
  }

  test('shows the allowance and the keep of every application', async () => {
    testApp.mock.onGet(url).reply(200, settings())
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('snapshotsWorkspaceSettings.usage')
    expect(
      wrapper.find('.snapshots-workspace-settings__keep-value').text()
    ).toBe('2')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('CRM')
    expect(rows[0].text()).toContain('snapshotsWorkspaceSettings.keepDefault')
    expect(rows[1].text()).toContain('Portal')
    expect(rows[1].find('.snapshots-workspace-settings__number').text()).toBe(
      '3'
    )
  })

  test('warns when the workspace is over its allowance', async () => {
    testApp.mock.onGet(url).reply(200, settings({ over_allowance: true }))
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('snapshotsWorkspaceSettings.overAllowance')
  })

  test('refuses a default keep above the maximum', async () => {
    testApp.mock.onGet(url).reply(200, settings())
    const wrapper = await mountComponent()

    wrapper
      .findAll('button')
      .find((button) => button.text() === 'snapshotKeep.change')
      .trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('4')
    await flushPromises()

    expect(
      wrapper.find('.snapshots-workspace-settings__error').text()
    ).toContain('snapshotKeep.errorAboveMaximum')
  })

  test('asks before a lower default keep deletes snapshots', async () => {
    testApp.mock.onGet(url).reply(200, settings())
    testApp.mock.onPatch(url).reply(200, settings({ default_keep: 1, used: 4 }))
    const wrapper = await mountComponent()

    wrapper
      .findAll('button')
      .find((button) => button.text() === 'snapshotKeep.change')
      .trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    // CRM follows the default and holds one unprotected snapshot beyond 1.
    expect(
      wrapper.find('.snapshots-workspace-settings__confirm').text()
    ).toContain('snapshotKeep.confirmDelete')
    expect(testApp.mock.history.patch).toHaveLength(0)

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'snapshotKeep.deleteAndSave')
      .trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      default_keep: 1,
      delete_snapshots: true,
    })
    expect(
      wrapper.find('.snapshots-workspace-settings__keep-value').text()
    ).toBe('1')
  })
})

describe('SnapshotsWorkspaceSettings over the allowance', () => {
  let testApp = null
  const workspace = { id: 12, name: 'Acme' }

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('never offers less than the current default keep', async () => {
    testApp.mock.onGet(`/snapshots/workspace/${workspace.id}/`).reply(200, {
      used: 30,
      limit: 25,
      over_allowance: true,
      blocked: false,
      snapshot_count: 0,
      default_keep: 2,
      max_keep: null,
      expiration_days: 360,
      applications: [1, 2, 3].map((id) => ({
        id,
        keep: null,
        snapshot_count: 0,
        protected_count: 0,
      })),
    })
    const wrapper = await testApp.mount(SnapshotsWorkspaceSettings, {
      props: { workspace },
    })
    await flushPromises()

    wrapper
      .findAll('button')
      .find((button) => button.text() === 'snapshotKeep.change')
      .trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('3')
    await flushPromises()

    expect(
      wrapper.find('.snapshots-workspace-settings__error').text()
    ).toContain('snapshotKeep.errorExceedsAllowance - 2')
  })
})
