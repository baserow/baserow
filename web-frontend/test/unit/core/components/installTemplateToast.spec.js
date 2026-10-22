import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import InstallTemplateToast from '@baserow/modules/core/components/toasts/InstallTemplateToast'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'

const runningJob = () => ({
  id: 10,
  type: 'install_template',
  state: 'started',
  progress_percentage: 64,
  workspace: { id: 1 },
  template: { id: 5, name: 'Applicant Tracker' },
  installed_applications: [],
  human_readable_error: '',
})

const database = {
  id: 1,
  name: 'Applicants',
  order: 1,
  type: 'database',
  workspace: { id: 1 },
  tables: [{ id: 11, name: 'Candidates', order: 1, database_id: 1 }],
}

describe('InstallTemplateToast', () => {
  let testApp = null
  let store = null
  let restoreApp = () => {}

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
    store.dispatch('workspace/forceCreate', { id: 1, name: 'First' })
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    restoreApp()
    restoreApp = () => {}
    await testApp.afterEach()
  })

  const installToasts = () =>
    store.state.toast.items.filter((toast) => toast.type === 'installTemplate')

  // Starts an install the way the template browser does: the toast first, then
  // the job.
  const startInstall = async (options = {}) => {
    await store.dispatch('toast/add', {
      type: 'installTemplate',
      data: { jobId: 10, template_name: 'Applicant Tracker' },
    })
    await store.dispatch('job/forceCreate', runningJob())
    const wrapper = await testApp.mount(InstallTemplateToast, {
      props: { toast: installToasts()[0] },
      ...options,
    })
    return wrapper
  }

  // The job type reads the flag from the app it was registered with.
  const disableFlag = () => {
    const jobType = testApp.$registry.get('job', 'install_template')
    const app = jobType.app
    jobType.app = Object.create(app, {
      $featureFlagIsEnabled: { value: () => false },
    })
    restoreApp = () => {
      jobType.app = app
    }
  }

  const endJob = async (data) => {
    const job = store.getters['job/get'](10)
    await store.dispatch('job/forceUpdate', { job, data })
    await flushPromises()
  }

  test('shows the progress, then the result with a link to the database', async () => {
    const select = vi
      .spyOn(testApp.$registry.get('application', 'database'), 'select')
      .mockResolvedValue(true)
    const wrapper = await startInstall()

    expect(wrapper.find('.toast__title').text()).toBe(
      'InstallTemplateJobType.installingTitle'
    )
    expect(wrapper.find('.toast__message').text()).toBe('64 %')
    expect(wrapper.find('.toast__loading').exists()).toBe(true)
    expect(wrapper.find('.toast__close').exists()).toBe(false)

    await endJob({ state: 'finished', installed_applications: [database] })

    // The job is gone from the store, the toast shows the result it was given.
    expect(store.getters['job/get'](10)).toBeUndefined()
    expect(store.getters['application/get'](1)).toBeDefined()
    expect(installToasts()).toHaveLength(1)
    expect(wrapper.find('.toast__icon--success').exists()).toBe(true)
    expect(wrapper.find('.toast__title').text()).toBe(
      'InstallTemplateJobType.installedMessage'
    )
    expect(wrapper.find('.install-template-toast__view').text()).toBe(
      'applicationType.viewDatabase'
    )
    // No legacy toast besides the install toast.
    expect(store.state.toast.items).toHaveLength(1)

    await wrapper.find('.install-template-toast__view').trigger('click')
    await flushPromises()

    expect(select).toHaveBeenCalledTimes(1)
    expect(select.mock.calls[0][0].id).toBe(1)
    expect(installToasts()).toHaveLength(0)
  })

  test('labels the link by the type of the installed application', async () => {
    const wrapper = await startInstall()

    await endJob({
      state: 'finished',
      installed_applications: [
        {
          id: 2,
          name: 'Portal',
          order: 1,
          type: 'builder',
          workspace: { id: 1 },
          pages: [],
        },
      ],
    })

    expect(wrapper.find('.install-template-toast__view').text()).toBe(
      'applicationType.viewBuilder'
    )
  })

  test('dismisses the result', async () => {
    const wrapper = await startInstall()
    await endJob({ state: 'finished', installed_applications: [database] })

    await wrapper.find('.install-template-toast__dismiss').trigger('click')

    expect(installToasts()).toHaveLength(0)
  })

  test('shows the reason of a failed install in the same toast', async () => {
    testApp.dontFailOnErrorResponses()
    const wrapper = await startInstall()

    await endJob({
      state: 'failed',
      human_readable_error: 'The template is blocked.',
    })

    expect(store.state.toast.items).toHaveLength(1)
    expect(wrapper.find('.toast__icon--error').exists()).toBe(true)
    expect(wrapper.find('.toast__title').text()).toBe(
      'InstallTemplateJobType.failedTitle'
    )
    expect(wrapper.find('.toast__message').text()).toBe(
      'The template is blocked.'
    )
    expect(wrapper.find('.install-template-toast__view').exists()).toBe(false)

    await wrapper.find('.toast__close').trigger('click')

    expect(installToasts()).toHaveLength(0)
  })

  test('shows the result in a new toast when the sidebar showed the progress', async () => {
    await store.dispatch('job/forceCreate', runningJob())

    await endJob({ state: 'finished', installed_applications: [database] })

    expect(installToasts()).toHaveLength(1)
    expect(installToasts()[0].data).toMatchObject({
      jobId: 10,
      state: 'finished',
      template_name: 'Applicant Tracker',
    })
  })

  test('removes the toast of a cancelled install', async () => {
    await startInstall()

    await endJob({ state: 'cancelled' })

    expect(installToasts()).toHaveLength(0)
    expect(store.getters['job/get'](10)).toBeUndefined()
  })

  test('removes the toast when its job leaves the store without ending', async () => {
    await startInstall()

    // Like when the target workspace is deleted or left during the install.
    await store.dispatch('job/deleteForWorkspace', { id: 1 })
    await flushPromises()

    expect(store.getters['job/get'](10)).toBeUndefined()
    expect(installToasts()).toHaveLength(0)
  })

  test('keeps the legacy notifications when the flag is off', async () => {
    disableFlag()
    await store.dispatch('job/forceCreate', runningJob())

    await endJob({ state: 'finished', installed_applications: [database] })

    expect(installToasts()).toHaveLength(0)
    expect(store.state.toast.items.map((toast) => toast.type)).toStrictEqual([
      'info-neutral',
    ])
  })

  test('removes a cancelled install from the sidebar when the flag is off', async () => {
    disableFlag()
    await store.dispatch('job/forceCreate', runningJob())

    await endJob({ state: 'cancelled' })

    expect(store.getters['job/get'](10)).toBeUndefined()
    expect(store.state.toast.items).toHaveLength(0)
  })

  test('keeps the legacy error when the flag is off', async () => {
    disableFlag()
    await store.dispatch('job/forceCreate', runningJob())

    await endJob({ state: 'failed', human_readable_error: 'Failed.' })

    expect(store.state.toast.items.map((toast) => toast.type)).toStrictEqual([
      'error',
    ])
  })

  test('renders an install toast once, next to the other toasts', async () => {
    await startInstall()
    await store.dispatch('toast/error', { title: 'Failed', message: 'Oops' })

    const wrapper = await testApp.mount(Toasts)

    expect(wrapper.findAll('.install-template-toast')).toHaveLength(1)
    expect(wrapper.findAll('.toast')).toHaveLength(2)
  })
})
