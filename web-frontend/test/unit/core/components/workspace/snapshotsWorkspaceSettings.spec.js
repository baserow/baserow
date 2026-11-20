import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import { permission } from '@baserow/test/helpers/permission'
import SnapshotsWorkspaceSettings from '@baserow/modules/core/components/workspace/SnapshotsWorkspaceSettings'

vi.mock('#app', async (importOriginal) =>
  (await import('@baserow/test/helpers/permission')).mockHasPermission(
    importOriginal
  )
)

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
    permission.check = () => true
    await testApp.afterEach()
  })

  const settings = (values = {}) => ({
    used: 5,
    limit: 25,
    over_allowance: false,
    snapshot_count: 4,
    default_max_snapshots: 2,
    max_snapshots_limit: 3,
    expiration_days: 360,
    applications: [
      { id: 1, max_snapshots: null, snapshot_count: 2, protected_count: 1 },
      { id: 2, max_snapshots: 3, snapshot_count: 2, protected_count: 0 },
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

  test('shows the allowance and the max snapshots of every application', async () => {
    testApp.mock.onGet(url).reply(200, settings())
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('snapshotsWorkspaceSettings.usage')
    expect(
      wrapper.find('.snapshots-workspace-settings__max-snapshots-value').text()
    ).toBe('2')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('CRM')
    expect(rows[0].text()).toContain(
      'snapshotsWorkspaceSettings.maxSnapshotsDefault'
    )
    expect(rows[1].text()).toContain('Portal')
    expect(rows[1].find('.snapshots-workspace-settings__number').text()).toBe(
      '3'
    )
  })

  test('tells non-admins that only admins can see the settings', async () => {
    permission.check = (operation) =>
      operation !== 'workspace.read_snapshot_settings'
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('snapshotsWorkspaceSettings.adminsOnly')
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('shows the plugin sections when the settings fail to load', async () => {
    const PluginSection = defineComponent({
      props: { workspace: Object, snapshotSettings: Object },
      setup: (props) => () =>
        h('div', { class: 'plugin-section' }, String(props.snapshotSettings)),
    })
    const plugin = Object.values(testApp.$registry.getAll('plugin'))[0]
    vi.spyOn(plugin, 'getWorkspaceSnapshotSettingsComponents').mockReturnValue([
      PluginSection,
    ])
    testApp.mock.onGet(url).reply(500, { error: 'ERROR' })
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('snapshotsWorkspaceSettings.loadFailed')
    expect(wrapper.find('.plugin-section').text()).toBe('null')
  })

  test('warns when the workspace is over its allowance', async () => {
    testApp.mock.onGet(url).reply(200, settings({ over_allowance: true }))
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('snapshotsWorkspaceSettings.overAllowance')
  })

  test('refuses a default max snapshots above the maximum', async () => {
    testApp.mock.onGet(url).reply(200, settings())
    const wrapper = await mountComponent()

    wrapper
      .findAll('button')
      .find((button) => button.text() === 'maxSnapshots.change')
      .trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('4')
    await flushPromises()

    expect(
      wrapper.find('.snapshots-workspace-settings__error').text()
    ).toContain('maxSnapshots.errorAboveMaximum')
  })

  test('asks before a lower default max snapshots deletes snapshots', async () => {
    testApp.mock.onGet(url).reply(200, settings())
    testApp.mock
      .onPatch(url)
      .reply(200, settings({ default_max_snapshots: 1, used: 4 }))
    const wrapper = await mountComponent()

    wrapper
      .findAll('button')
      .find((button) => button.text() === 'maxSnapshots.change')
      .trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    // CRM follows the default and holds one unprotected snapshot beyond 1.
    expect(
      wrapper.find('.snapshots-workspace-settings__confirm').text()
    ).toContain('maxSnapshots.confirmDelete')
    expect(testApp.mock.history.patch).toHaveLength(0)

    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'maxSnapshots.deleteAndSave')
      .trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      default_max_snapshots: 1,
      delete_snapshots: true,
    })
    expect(
      wrapper.find('.snapshots-workspace-settings__max-snapshots-value').text()
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
    permission.check = () => true
    await testApp.afterEach()
  })

  test('never offers less than the current default max snapshots', async () => {
    testApp.mock.onGet(`/snapshots/workspace/${workspace.id}/`).reply(200, {
      used: 30,
      limit: 25,
      over_allowance: true,
      blocked: false,
      snapshot_count: 0,
      default_max_snapshots: 2,
      max_snapshots_limit: null,
      expiration_days: 360,
      applications: [1, 2, 3].map((id) => ({
        id,
        max_snapshots: null,
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
      .find((button) => button.text() === 'maxSnapshots.change')
      .trigger('click')
    await flushPromises()
    await wrapper.find('input').setValue('3')
    await flushPromises()

    expect(
      wrapper.find('.snapshots-workspace-settings__error').text()
    ).toContain('maxSnapshots.errorExceedsAllowance - 2')
  })
})
