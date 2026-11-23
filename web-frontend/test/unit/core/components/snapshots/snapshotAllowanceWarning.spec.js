import { flushPromises } from '@vue/test-utils'
import { vi } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import { permission } from '@baserow/test/helpers/permission'
import SnapshotAllowanceWarning from '@baserow/modules/core/components/snapshots/SnapshotAllowanceWarning'

vi.mock('#app', async (importOriginal) =>
  (await import('@baserow/test/helpers/permission')).mockHasPermission(
    importOriginal
  )
)

describe('SnapshotAllowanceWarning', () => {
  let testApp = null
  const workspace = { id: 12, name: 'Acme' }
  const url = `/snapshots/workspace/${workspace.id}/`

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    permission.check = () => true
    await testApp.afterEach()
  })

  const settings = (values) => ({
    used: 2,
    limit: 3,
    over_allowance: false,
    blocked: false,
    snapshot_count: 0,
    default_max_snapshots: 2,
    max_snapshots_limit: null,
    expiration_days: 360,
    applications: [],
    ...values,
  })

  const mountWarning = async () => {
    const wrapper = await testApp.mount(SnapshotAllowanceWarning, {
      props: { workspace },
    })
    await flushPromises()
    return wrapper
  }

  test('warns when the new application takes the workspace over', async () => {
    testApp.mock.onGet(url).reply(200, settings())
    const wrapper = await mountWarning()

    expect(wrapper.text()).toContain('snapshotAllowanceWarning.overAllowance')
  })

  test('says nothing when it stays within the allowance', async () => {
    testApp.mock.onGet(url).reply(200, settings({ limit: 10 }))
    const wrapper = await mountWarning()

    expect(wrapper.text()).toBe('')
  })

  test('says nothing when the default max snapshots is 0 or there is no limit', async () => {
    testApp.mock.onGet(url).reply(200, settings({ default_max_snapshots: 0 }))
    expect((await mountWarning()).text()).toBe('')
  })

  test('says nothing to users who cannot read the settings', async () => {
    permission.check = (operation) =>
      operation !== 'workspace.read_snapshot_settings'
    const wrapper = await mountWarning()

    expect(wrapper.text()).toBe('')
    expect(testApp.mock.history.get).toHaveLength(0)
  })
})
