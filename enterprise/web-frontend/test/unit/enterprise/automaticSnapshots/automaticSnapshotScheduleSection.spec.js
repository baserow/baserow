import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { defineComponent } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AutomaticSnapshotScheduleSection from '@baserow_enterprise/components/automaticSnapshots/AutomaticSnapshotScheduleSection'

// Turns the automatic snapshots feature flag off in the tests that ask for it.
const { flags } = vi.hoisted(() => ({
  flags: { automaticSnapshotsOff: false },
}))
mockNuxtImport('useNuxtApp', (original) => () => {
  const nuxtApp = original()
  if (!flags.automaticSnapshotsOff) {
    return nuxtApp
  }
  return new Proxy(nuxtApp, {
    get(target, property, receiver) {
      if (property === '$featureFlagIsEnabled') {
        return (flag) => flag !== 'automatic_snapshots'
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
  last_run_at: null,
  last_error: '',
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
    await testApp.afterEach()
  })

  const giveEnterpriseLicense = () => {
    testApp.store.dispatch('auth/forceUpdateUserData', {
      active_licenses: { instance_wide: { enterprise: true } },
    })
  }

  const mountComponent = async (snapshotUsage = null) => {
    const wrapper = await testApp.mount(AutomaticSnapshotScheduleSection, {
      props: { application, snapshotUsage },
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

  test('offers to set up a schedule when nothing applies', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).reply(200, overview())

    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.none')
    expect(wrapper.text()).toContain('automaticSnapshots.setUp')
    expect(wrapper.find('.switch').exists()).toBe(false)
    expect(wrapper.classes()).toContain('automatic-snapshot-schedule--empty')
  })

  test('turns an application off from the workspace schedule', async () => {
    giveEnterpriseLicense()
    testApp.mock
      .onGet(url)
      .replyOnce(200, overview({ workspace_default: schedule() }))
    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.badgeWorkspace')
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

  test('shows the own schedule and its last error', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).reply(
      200,
      overview({
        state: 'own_schedule',
        schedule: schedule({
          application_id: 10,
          last_error: 'The workspace has reached its snapshot limit.',
        }),
      })
    )

    const wrapper = await mountComponent()

    expect(wrapper.text()).toContain('automaticSnapshots.badgeOwn')
    expect(wrapper.text()).toContain('automaticSnapshots.lastError')
    expect(wrapper.find('.switch').classes()).toContain('switch--active')
    expect(footerLabels(wrapper)).toEqual([
      'automaticSnapshots.edit',
      'automaticSnapshots.remove',
    ])
  })

  test('warns that runs skip an application that keeps no snapshots', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).reply(
      200,
      overview({
        state: 'own_schedule',
        schedule: schedule({ application_id: 10 }),
      })
    )

    const wrapper = await mountComponent({ limit: 10, effective_keep: 0 })

    expect(wrapper.find('.automatic-snapshot-schedule__warning').text()).toBe(
      'automaticSnapshots.keepsNoneWarning'
    )
  })

  test('warns that runs fail when snapshots are turned off', async () => {
    giveEnterpriseLicense()
    testApp.mock.onGet(url).reply(
      200,
      overview({
        state: 'own_schedule',
        schedule: schedule({ application_id: 10 }),
      })
    )

    const wrapper = await mountComponent({ limit: 0, effective_keep: 2 })

    expect(wrapper.find('.automatic-snapshot-schedule__warning').text()).toBe(
      'automaticSnapshots.disabledWarning'
    )
  })

  test('is hidden without the automatic snapshots feature flag', async () => {
    giveEnterpriseLicense()
    flags.automaticSnapshotsOff = true

    const wrapper = await mountComponent()

    expect(wrapper.find('.automatic-snapshot-schedule').exists()).toBe(false)
    expect(testApp.mock.history.get).toHaveLength(0)
  })
})
