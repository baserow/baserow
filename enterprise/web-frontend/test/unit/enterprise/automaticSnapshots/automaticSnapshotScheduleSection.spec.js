import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AutomaticSnapshotScheduleSection from '@baserow_enterprise/components/automaticSnapshots/AutomaticSnapshotScheduleSection'

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

const PaidFeaturesModalStub = defineComponent({
  name: 'PaidFeaturesModal',
  methods: {
    show() {},
  },
  template: '<div class="paid-features-modal-stub"></div>',
})

const schedule = (values = {}) => ({
  id: 1,
  application_id: null,
  enabled: true,
  interval: 'DAY',
  timezone: 'UTC',
  minute: 0,
  hour: 2,
  day_of_week: 0,
  day_of_month: 1,
  next_run_at: '2026-11-05T02:00:00Z',
  paused_reason: null,
  ...values,
})

const overview = (values = {}) => ({
  state: 'workspace_default',
  schedule: null,
  workspace_default: null,
  min_interval_minutes: 60,
  ...values,
})

describe('AutomaticSnapshotScheduleSection', () => {
  let testApp = null
  const workspace = { id: 1, name: 'Workspace' }
  const application = { id: 10, name: 'CRM', workspace }
  const url = `/automatic-snapshots/application/${application.id}/`

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    flags.automaticSnapshotsOff = false
    flags.noReadPermission = false
    await testApp.afterEach()
  })

  const giveEnterpriseLicense = () => {
    testApp.store.dispatch('auth/forceUpdateUserData', {
      active_licenses: { instance_wide: { enterprise: true } },
    })
  }

  const mountComponent = async () => {
    const wrapper = await testApp.mount(AutomaticSnapshotScheduleSection, {
      props: { application },
      global: { stubs: { PaidFeaturesModal: PaidFeaturesModalStub } },
    })
    await flushPromises()
    return wrapper
  }

  const footerLabels = (wrapper) =>
    wrapper
      .findAll('.automatic-snapshot-schedule__footer button')
      .map((button) => button.text())

  test('shows the upsell without the license', async () => {
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.upsell')
    expect(wrapper.text()).toContain('automaticSnapshots.enterpriseBadge')
    expect(wrapper.find('.paid-features-modal-stub').exists()).toBe(true)
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('hides schedule details and clears its active state when the license is lost', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).reply(
      200,
      overview({
        workspace_default: schedule(),
        last_run: { finished_at: '2026-11-24T08:00:00Z', error: 'No room' },
      })
    )
    const wrapper = await mountComponent()
    expect(
      wrapper.find('.automatic-snapshot-schedule__last-run').exists()
    ).toBe(true)
    await testApp.store.dispatch('auth/forceUpdateUserData', {
      active_licenses: {
        instance_wide: { enterprise: false },
        per_workspace: {},
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('automaticSnapshots.upsell')
    expect(
      wrapper.find('.automatic-snapshot-schedule__last-run').exists()
    ).toBe(false)
    expect(wrapper.find('.switch').exists()).toBe(false)
    expect(wrapper.emitted('capacity-warning').at(-1)).toEqual([''])
  })

  test('offers to set up a schedule when nothing applies', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).reply(200, overview())

    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.none')
    expect(wrapper.text()).toContain('automaticSnapshots.setUp')
    expect(wrapper.find('.switch').exists()).toBe(false)
    expect(wrapper.classes()).toContain('automatic-snapshot-schedule--empty')
  })

  test.each(['', 'No room for this application'])(
    'shows the last application result with optional details: %s',
    async (error) => {
      giveEnterpriseLicense()
      testApp.mock.onGet(url).reply(
        200,
        overview({
          workspace_default: schedule(),
          last_run: { finished_at: '2026-11-24T08:00:00Z', error },
        })
      )
      const wrapper = await mountComponent()
      const result = wrapper.find('.automatic-snapshot-schedule__last-run')
      expect(result.text()).toContain('automaticSnapshots.lastExecution:')
      expect(wrapper.text()).not.toContain(
        'automaticSnapshots.upToMaxSnapshots'
      )
      expect(result.html()).toMatchSnapshot()
      expect(result.text()).toContain(
        error
          ? 'automaticSnapshots.executionFailed'
          : 'automaticSnapshots.executionSucceeded'
      )
      expect(result.find('details').exists()).toBe(true)
      if (error) {
        expect(result.find('details').attributes('open')).toBeUndefined()
        expect(result.find('summary').attributes('aria-label')).toBe(
          'automaticSnapshots.executionDetails'
        )
        expect(
          result.find('.automatic-snapshot-schedule__last-run-error').text()
        ).toContain(error)
      }
    }
  )

  test('turns an application off from the workspace schedule', async () => {
    giveEnterpriseLicense()
    testApp.mock
      .onGet(url)
      .replyOnce(200, overview({ workspace_default: schedule() }))
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.badgeWorkspace')
    expect(wrapper.emitted('capacity-warning').at(-1)).toEqual([
      'automaticSnapshots.scheduleBlocked',
    ])
    expect(wrapper.text()).toContain('automaticSnapshots.everyDay')
    expect(wrapper.text()).toContain('automaticSnapshots.setByWorkspace')
    expect(footerLabels(wrapper)).toEqual(['automaticSnapshots.customise'])

    testApp.mock.onPost(url).reply(200, schedule({ enabled: false }))
    testApp.mock.onGet(url).replyOnce(
      200,
      overview({
        state: 'off',
        schedule: schedule({ application_id: 10, enabled: false }),
        workspace_default: schedule(),
      })
    )
    await wrapper.find('.switch').trigger('click')
    await flushPromises()

    const posted = JSON.parse(testApp.mock.history.post[0].data)
    expect(posted).toMatchObject({ enabled: false, interval: 'DAY', hour: 2 })
    expect(wrapper.text()).toContain('automaticSnapshots.badgeOff')
    expect(wrapper.text()).toContain('automaticSnapshots.off')
    expect(footerLabels(wrapper)).toEqual([
      'automaticSnapshots.edit',
      'automaticSnapshots.resetToWorkspace',
    ])
  })

  test('shows the own schedule', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).reply(
      200,
      overview({
        state: 'own_schedule',
        schedule: schedule({
          application_id: 10,
        }),
      })
    )

    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.badgeOwn')
    expect(wrapper.find('.switch').classes()).toContain('switch--active')
    expect(footerLabels(wrapper)).toEqual([
      'automaticSnapshots.edit',
      'automaticSnapshots.remove',
    ])
  })

  test('is hidden without the automatic snapshots feature flag', async () => {
    giveEnterpriseLicense()
    flags.automaticSnapshotsOff = true

    const wrapper = await mountComponent()

    expect(wrapper.find('.automatic-snapshot-schedule').exists()).toBe(false)
    expect(testApp.mock.history.get).toHaveLength(0)
  })

  test('offers to retry when the schedule can not be loaded', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).replyOnce(500).onGet(url).reply(200, overview())

    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.loadFailed')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === 'action.retry')
      .trigger('click')
    await flushPromises()

    expect(testApp.mock.history.get).toHaveLength(2)
    expect(wrapper.text()).not.toContain('automaticSnapshots.loadFailed')
    expect(wrapper.text()).toContain('automaticSnapshots.setUp')
  })

  test('is hidden without the permission to read the schedule', async () => {
    giveEnterpriseLicense()
    flags.noReadPermission = true

    const wrapper = await mountComponent()

    expect(wrapper.find('.automatic-snapshot-schedule').exists()).toBe(false)
    expect(testApp.mock.history.get).toHaveLength(0)
  })
})
