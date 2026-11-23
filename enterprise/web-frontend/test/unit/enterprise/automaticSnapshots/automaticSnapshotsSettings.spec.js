import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AutomaticSnapshotsSettings from '@baserow_enterprise/components/automaticSnapshots/AutomaticSnapshotsSettings'

// Turns the automatic snapshots feature flag off, or takes away the permission
// to read the schedules, in the tests that ask for it.
const { flags } = vi.hoisted(() => ({
  flags: { automaticSnapshotsOff: false, noReadPermission: false },
}))
mockNuxtImport('useNuxtApp', (original) => () => {
  const nuxtApp = original()
  if (!flags.automaticSnapshotsOff && !flags.noReadPermission) {
    return nuxtApp
  }
  return new Proxy(nuxtApp, {
    get(target, property, receiver) {
      if (property === '$featureFlagIsEnabled' && flags.automaticSnapshotsOff) {
        return (flag) => flag !== 'automatic_snapshots'
      }
      if (property === '$hasPermission' && flags.noReadPermission) {
        return (operation) =>
          !operation.endsWith('read_automatic_snapshot_schedule')
      }
      return Reflect.get(target, property, receiver)
    },
  })
})

const schedule = (values = {}) => ({
  id: 1,
  application_id: null,
  enabled: true,
  interval: 'WEEK',
  timezone: 'Europe/Amsterdam',
  minute: 30,
  hour: 6,
  day_of_week: 0,
  day_of_month: 1,
  next_run_at: '2026-11-09T05:30:00Z',
  last_run_at: null,
  last_error: '',
  paused_reason: null,
  ...values,
})

describe('AutomaticSnapshotsSettings', () => {
  let testApp = null
  const workspace = { id: 34, name: 'Snapshots test' }
  const url = `/automatic-snapshots/workspace/${workspace.id}/`

  const application = (id, name, type = 'database') => ({
    id,
    name,
    type,
    order: id,
    workspace,
  })

  beforeEach(() => {
    testApp = new TestApp()
    testApp.store.dispatch('auth/forceUpdateUserData', {
      active_licenses: { instance_wide: { enterprise: true } },
    })
    testApp.store.commit('application/SET_ITEMS', [
      application(1, 'CRM'),
      application(2, 'Portal', 'builder'),
      application(3, 'Archive'),
      // An application of another workspace is never listed.
      { ...application(4, 'Elsewhere'), workspace: { id: 99 } },
    ])
  })

  afterEach(async () => {
    flags.automaticSnapshotsOff = false
    flags.noReadPermission = false
    await testApp.afterEach()
  })

  const response = (values = {}) => ({
    workspace_default: schedule(),
    application_schedules: [
      schedule({
        id: 2,
        application_id: 1,
        interval: 'DAY',
        hour: 2,
        minute: 0,
        last_error: 'The workspace has reached its snapshot limit.',
      }),
      schedule({ id: 3, application_id: 3, enabled: false }),
    ],
    min_interval_minutes: 60,
    ...values,
  })

  const mountComponent = async (snapshotSettings = null) => {
    const wrapper = await testApp.mount(AutomaticSnapshotsSettings, {
      props: { workspace, snapshotSettings },
      global: { stubs: { PaidFeaturesModal: true } },
    })
    await flushPromises()
    return wrapper
  }

  test('shows the upsell without the license', async () => {
    testApp.store.dispatch('auth/forceUpdateUserData', {
      active_licenses: { instance_wide: { enterprise: false } },
    })
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshotsSettings.upsell')
    expect(wrapper.find('table').exists()).toBe(false)
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('lists every application with the schedule it follows', async () => {
    testApp.mock.onGet(url).reply(200, response())
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshotsSettings.covers')
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('CRM')
    expect(rows[0].text()).toContain('automaticSnapshots.badgeOwn')
    expect(
      rows[0].find('.automatic-snapshots-settings__error-icon').exists()
    ).toBe(true)
    expect(rows[1].text()).toContain('Portal')
    expect(rows[1].text()).toContain('automaticSnapshots.badgeWorkspace')
    expect(rows[1].text()).toContain('automaticSnapshots.everyWeek')
    expect(rows[2].text()).toContain('automaticSnapshots.badgeOff')
  })

  test('warns about scheduled applications that runs can not snapshot', async () => {
    testApp.mock.onGet(url).reply(200, response())
    const wrapper = await mountComponent({
      limit: 10,
      default_max_snapshots: 0,
      applications: [
        // At its own max, and every snapshot is protected.
        { id: 1, max_snapshots: 3, snapshot_count: 3, protected_count: 3 },
        // Follows the default of 0, so runs skip it.
        { id: 2, max_snapshots: null, snapshot_count: 0, protected_count: 0 },
        // Turned off, so there's nothing to warn about.
        { id: 3, max_snapshots: 1, snapshot_count: 1, protected_count: 1 },
      ],
    })

    // Each warning goes on its own row, below the row of its application.
    const rows = wrapper.findAll('tbody tr')
    const warningAfter = (name) => {
      const index = rows.findIndex((row) => row.text().includes(name))
      const next = rows[index + 1]
      return next?.classes('automatic-snapshots-settings__warning-row')
        ? next.text()
        : ''
    }
    expect(warningAfter('CRM')).toContain(
      'automaticSnapshots.fullOfProtectedWarningShort'
    )
    expect(warningAfter('Portal')).toContain(
      'automaticSnapshots.maxSnapshotsZeroWarningShort'
    )
    expect(warningAfter('Archive')).toBe('')
  })

  test('offers to set up a workspace schedule when there is none', async () => {
    testApp.mock.onGet(url).reply(200, response({ workspace_default: null }))
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain(
      'automaticSnapshotsSettings.workspaceScheduleNone'
    )
    // Without a workspace schedule, nothing applies to Portal.
    expect(wrapper.findAll('tbody tr')[1].text()).toContain(
      'automaticSnapshotsSettings.badgeNotScheduled'
    )
  })

  const openRowMenu = async (wrapper, index) => {
    await wrapper.findAll('tbody tr')[index].find('button').trigger('click')
    return document.body.querySelector('.context__menu').textContent
  }

  test('only offers to turn off applications that are scheduled', async () => {
    testApp.mock
      .onGet(url)
      .reply(200, response({ workspace_default: schedule({ enabled: false }) }))
    const wrapper = await mountComponent()

    // Nothing schedules Portal, because the workspace schedule is off.
    const portalMenu = await openRowMenu(wrapper, 1)
    expect(portalMenu).not.toContain('automaticSnapshotsSettings.turnOff')
    expect(portalMenu).not.toContain('automaticSnapshotsSettings.turnOn')

    const crmMenu = await openRowMenu(wrapper, 0)
    expect(crmMenu).toContain('automaticSnapshotsSettings.turnOff')
  })

  test('drops removed applications from the selection', async () => {
    testApp.mock.onGet(url).reply(200, response())
    testApp.mock.onPost(`${url}bulk/`).reply(204)
    const wrapper = await mountComponent()

    const checkboxes = wrapper.findAll('tbody .checkbox')
    await checkboxes[0].trigger('click')
    await checkboxes[2].trigger('click')
    // Someone else deletes Archive while the page is open.
    testApp.store.commit('application/DELETE_ITEM', 3)
    await flushPromises()

    const resetButton = wrapper
      .findAll('.automatic-snapshots-settings__bulk button')
      .find((button) => button.text() === 'automaticSnapshots.resetToWorkspace')
    await resetButton.trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      application_ids: [1],
      action: 'reset',
    })
  })

  test('searches and pages the applications', async () => {
    testApp.store.commit(
      'application/SET_ITEMS',
      Array.from({ length: 23 }, (_, index) =>
        application(index + 1, `Application ${index + 1}`)
      )
    )
    testApp.mock.onGet(url).reply(200, response({ application_schedules: [] }))
    const wrapper = await mountComponent()

    expect(wrapper.findAll('tbody tr')).toHaveLength(5)
    expect(wrapper.find('.paginator').exists()).toBe(true)
    expect(
      wrapper.find('.automatic-snapshots-settings__pagination').exists()
    ).toBe(true)

    await wrapper
      .find('.automatic-snapshots-settings__search input')
      .setValue('Application 2')
    // "Application 2" and "Application 20" to "Application 23".
    const names = wrapper
      .findAll('.automatic-snapshots-settings__application-name')
      .map((name) => name.text())
    expect(names).toEqual([
      'Application 2',
      'Application 20',
      'Application 21',
      'Application 22',
      'Application 23',
    ])
    expect(
      wrapper.find('.automatic-snapshots-settings__pagination').exists()
    ).toBe(false)
  })

  test('resets the selected applications to the workspace schedule', async () => {
    testApp.mock.onGet(url).reply(200, response())
    testApp.mock.onPost(`${url}bulk/`).reply(204)
    const wrapper = await mountComponent()

    const checkboxes = wrapper.findAll('tbody .checkbox')
    await checkboxes[0].trigger('click')
    await checkboxes[2].trigger('click')
    expect(wrapper.text()).toContain('automaticSnapshotsSettings.selected')

    const resetButton = wrapper
      .findAll('.automatic-snapshots-settings__bulk button')
      .find((button) => button.text() === 'automaticSnapshots.resetToWorkspace')
    await resetButton.trigger('click')
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.post[0].data)).toEqual({
      application_ids: [1, 3],
      action: 'reset',
    })
    expect(wrapper.find('.automatic-snapshots-settings__bulk').exists()).toBe(
      false
    )
  })

  test('is hidden without the automatic snapshots feature flag', async () => {
    flags.automaticSnapshotsOff = true

    const wrapper = await mountComponent()

    expect(wrapper.find('.automatic-snapshots-settings').exists()).toBe(false)
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('offers to remove own schedules when there is no workspace schedule', async () => {
    testApp.mock.onGet(url).reply(200, response({ workspace_default: null }))
    const wrapper = await mountComponent()

    const crmMenu = await openRowMenu(wrapper, 0)
    expect(crmMenu).toContain('automaticSnapshots.remove')
    expect(crmMenu).not.toContain('automaticSnapshots.resetToWorkspace')

    await wrapper.findAll('tbody .checkbox')[0].trigger('click')
    const bulkLabels = wrapper
      .findAll('.automatic-snapshots-settings__bulk button')
      .map((button) => button.text())
    expect(bulkLabels).toContain('automaticSnapshots.remove')
    expect(bulkLabels).not.toContain('automaticSnapshots.resetToWorkspace')
  })

  test('offers to retry when the schedules can not be loaded', async () => {
    testApp.mock.onGet(url).replyOnce(500).onGet(url).reply(200, response())
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.loadFailed')
    await wrapper
      .find('.automatic-snapshots-settings__load-failed button')
      .trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('automaticSnapshots.loadFailed')
    expect(wrapper.find('table').exists()).toBe(true)
  })

  test('is hidden without the permission to read the schedules', async () => {
    flags.noReadPermission = true

    const wrapper = await mountComponent()

    expect(wrapper.find('.automatic-snapshots-settings').exists()).toBe(false)
    expect(testApp.mock.history.get).toHaveLength(0)
  })
})
