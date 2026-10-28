import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import { updateJob } from '@baserow/test/helpers/store'
import { triggerDownload } from '@baserow/modules/core/utils/download'
import DownloadTemplateToast from '@baserow/modules/core/components/toasts/DownloadTemplateToast'

// Saving the file is replaced, so that nothing navigates.
vi.mock('@baserow/modules/core/utils/download', async (importOriginal) => {
  const original = await importOriginal()
  return { ...original, triggerDownload: vi.fn() }
})

const runningJob = () => ({
  id: 10,
  type: 'download_user_template',
  state: 'started',
  progress_percentage: 40,
  human_readable_error: '',
  url: null,
  file_name: 'project-tracker.zip',
})

const template = { name: 'Project Tracker', slug: 'project-tracker-a1b2c3' }

const archive = {
  url: 'http://localhost:8000/media/template-archives/1/abc_def.zip',
  file_name: 'project-tracker.zip',
}

describe('DownloadTemplateToast', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    testApp.authenticate({ id: 1, preferences: {}, completed_onboarding: true })
  })

  afterEach(async () => {
    vi.restoreAllMocks()
    vi.mocked(triggerDownload).mockReset()
    await testApp.afterEach()
  })

  const jobType = () => testApp.$registry.get('job', 'download_user_template')

  const downloadToasts = () =>
    store.state.toast.items.filter((toast) => toast.type === 'downloadTemplate')

  const errorToasts = () =>
    store.state.toast.items.filter((toast) => toast.type === 'error')

  // Starts a download the way a click does: the toast first, then the job.
  const startDownload = async () => {
    const job = runningJob()
    await jobType().addDownloadToast(job, template)
    await store.dispatch('job/forceCreate', job)
    return await testApp.mount(DownloadTemplateToast, {
      props: { toast: downloadToasts()[0] },
    })
  }

  test('names the template, then saves the archive once and keeps a button for it', async () => {
    const t = vi.spyOn(testApp.nuxtApp.$i18n, 't')
    const wrapper = await startDownload()

    expect(t).toHaveBeenCalledWith('downloadTemplateToast.preparingMessage', {
      name: template.name,
    })
    expect(triggerDownload).not.toHaveBeenCalled()

    await updateJob(store, 10, { state: 'finished', ...archive })

    expect(triggerDownload).toHaveBeenCalledTimes(1)
    expect(triggerDownload).toHaveBeenCalledWith(
      archive.url,
      archive.file_name,
      { viaXhr: false }
    )

    await wrapper.find('.download-template-toast__download').trigger('click')
    await flushPromises()

    expect(triggerDownload).toHaveBeenCalledTimes(2)

    await wrapper.find('.download-template-toast__dismiss').trigger('click')

    expect(downloadToasts()).toHaveLength(0)
  })

  test('shows the reason of a failed download in the same toast', async () => {
    const wrapper = await startDownload()

    await updateJob(store, 10, {
      state: 'failed',
      human_readable_error: 'The content of the template was removed.',
    })

    expect(store.state.toast.items).toHaveLength(1)
    expect(wrapper.find('.toast__message').text()).toBe(
      'The content of the template was removed.'
    )
    expect(wrapper.find('.download-template-toast__download').exists()).toBe(
      false
    )

    await wrapper.find('.toast__close').trigger('click')

    expect(downloadToasts()).toHaveLength(0)
  })

  test('adds one toast when a click gets a job that already has one', async () => {
    await startDownload()

    // Another click got the same job, which was started by this or another user.
    await jobType().addDownloadToast(runningJob(), template)
    await store.dispatch('job/create', runningJob())

    expect(downloadToasts()).toHaveLength(1)
    expect(store.getters['job/getAll']).toHaveLength(1)

    await updateJob(store, 10, { state: 'finished', ...archive })

    expect(triggerDownload).toHaveBeenCalledTimes(1)
  })

  test('replaces the ended toasts of the same download when it is clicked again', async () => {
    await startDownload()
    await updateJob(store, 10, { state: 'finished', ...archive })
    await jobType().addDownloadToast({ ...runningJob(), id: 11 }, template)
    await store.dispatch('job/forceCreate', { ...runningJob(), id: 11 })
    await updateJob(store, 11, { state: 'failed', human_readable_error: 'x' })
    // The latest revision of the same template, and a running download.
    await jobType().addDownloadToast({ ...runningJob(), id: 12 }, template, {
      latest: true,
    })
    await store.dispatch('job/forceCreate', { ...runningJob(), id: 12 })
    await updateJob(store, 12, { state: 'finished', ...archive })
    const other = { name: 'Roadmap', slug: 'roadmap-g7h8i9' }
    await jobType().addDownloadToast({ ...runningJob(), id: 13 }, other)
    await store.dispatch('job/forceCreate', { ...runningJob(), id: 13 })

    await jobType().addDownloadToast({ ...runningJob(), id: 14 }, template)

    const jobIds = () =>
      downloadToasts()
        .map((toast) => toast.data.jobId)
        .sort()
    // Only the finished 10 and the failed 11 are replaced by 14.
    expect(jobIds()).toStrictEqual([12, 13, 14])

    // A click that gets the running job of a template keeps its toast.
    await jobType().addDownloadToast({ ...runningJob(), id: 13 }, other)

    expect(jobIds()).toStrictEqual([12, 13, 14])
  })

  test('only shows the button for a download started before the page was loaded', async () => {
    // The pending jobs are fetched when the page loads, without their toast.
    await store.dispatch('job/forceCreate', runningJob())

    await updateJob(store, 10, { state: 'finished', ...archive })

    expect(triggerDownload).not.toHaveBeenCalled()
    expect(downloadToasts()).toHaveLength(1)
    const t = vi.spyOn(testApp.nuxtApp.$i18n, 't')
    const wrapper = await testApp.mount(DownloadTemplateToast, {
      props: { toast: downloadToasts()[0] },
    })

    // Without the template, it's named after the file.
    expect(t).toHaveBeenCalledWith('downloadTemplateToast.readyMessage', {
      name: archive.file_name,
    })

    await wrapper.find('.download-template-toast__download').trigger('click')
    await flushPromises()

    expect(triggerDownload).toHaveBeenCalledTimes(1)
  })

  test('shows an error when the archive cannot be saved', async () => {
    await startDownload()
    vi.mocked(triggerDownload).mockRejectedValueOnce(new Error('403'))

    await updateJob(store, 10, { state: 'finished', ...archive })

    expect(errorToasts().map((toast) => toast.title)).toStrictEqual([
      'clientHandler.notCompletedTitle',
    ])
    expect(downloadToasts()).toHaveLength(1)
  })
})
