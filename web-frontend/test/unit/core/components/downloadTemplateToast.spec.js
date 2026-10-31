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

const template = { name: 'Project Tracker', slug: 'project-tracker-a1b2c3' }

const runningJob = (data = {}) => ({
  id: 10,
  type: 'download_user_template',
  state: 'started',
  progress_percentage: 40,
  human_readable_error: '',
  slug: template.slug,
  latest: false,
  ...data,
})

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

  // What the download endpoint answers once the job ends.
  const mockDownload = (slug = template.slug) =>
    testApp.mock.onPost(`/templates/${slug}/download/`)

  const downloadRequests = () =>
    testApp.mock.history.post.map((request) => [
      request.url,
      JSON.parse(request.data),
    ])

  // Shows what a click got from the download endpoint.
  const click = (response, { of = template, latest = false } = {}) =>
    jobType().startDownload(response, of, { latest })

  const mountToast = async (toast = downloadToasts()[0]) =>
    await testApp.mount(DownloadTemplateToast, { props: { toast } })

  // A click that got the job building the archive.
  const startDownload = async () => {
    await click({ status: 202, data: runningJob() })
    return await mountToast()
  }

  test('names the template, then asks for the archive once the job ends, saves it once and keeps a button for it', async () => {
    const t = vi.spyOn(testApp.nuxtApp.$i18n, 't')
    const wrapper = await startDownload()
    mockDownload().replyOnce(200, archive)

    expect(t).toHaveBeenCalledWith('downloadTemplateToast.preparingMessage', {
      name: template.name,
    })
    expect(triggerDownload).not.toHaveBeenCalled()

    await updateJob(store, 10, { state: 'finished' })

    expect(downloadRequests()).toStrictEqual([
      [`/templates/${template.slug}/download/`, { latest: false }],
    ])
    expect(triggerDownload).toHaveBeenCalledTimes(1)
    expect(triggerDownload).toHaveBeenCalledWith(
      archive.url,
      archive.file_name,
      { viaXhr: false }
    )
    expect(store.getters['job/getAll']).toHaveLength(0)

    await wrapper.find('.download-template-toast__download').trigger('click')
    await flushPromises()

    expect(triggerDownload).toHaveBeenCalledTimes(2)

    await wrapper.find('.download-template-toast__dismiss').trigger('click')

    expect(downloadToasts()).toHaveLength(0)
  })

  test('does not hold the polling while the archive is saved, and disables its button meanwhile', async () => {
    const wrapper = await startDownload()
    mockDownload().replyOnce(200, archive)
    let saved = null
    vi.mocked(triggerDownload).mockReturnValueOnce(
      new Promise((resolve) => (saved = resolve))
    )

    await updateJob(store, 10, { state: 'finished' })

    expect(store.getters['job/getAll']).toHaveLength(0)
    const button = wrapper.find('.download-template-toast__download')
    expect(button.attributes('disabled')).toBeDefined()

    saved()
    await flushPromises()

    expect(button.attributes('disabled')).toBeUndefined()
  })

  test('follows the new job when the archive has to be built again', async () => {
    const wrapper = await startDownload()
    mockDownload().replyOnce(202, runningJob({ id: 11 }))

    await updateJob(store, 10, { state: 'finished' })

    expect(downloadToasts().map((toast) => toast.data.jobId)).toStrictEqual([
      11,
    ])
    expect(store.getters['job/getAll'].map((job) => job.id)).toStrictEqual([11])
    expect(wrapper.find('.download-template-toast__download').exists()).toBe(
      false
    )
    expect(triggerDownload).not.toHaveBeenCalled()

    mockDownload().replyOnce(200, archive)
    await updateJob(store, 11, { state: 'finished' })

    expect(triggerDownload).toHaveBeenCalledTimes(1)
    expect(wrapper.find('.download-template-toast__download').exists()).toBe(
      true
    )
  })

  test('saves the archive once when a click gets it ready', async () => {
    await click({ status: 200, data: archive })
    const t = vi.spyOn(testApp.nuxtApp.$i18n, 't')
    const wrapper = await mountToast()

    expect(t).toHaveBeenCalledWith('downloadTemplateToast.readyTitle')
    expect(triggerDownload).toHaveBeenCalledTimes(1)
    expect(store.getters['job/getAll']).toHaveLength(0)

    await wrapper.find('.download-template-toast__download').trigger('click')
    await flushPromises()

    expect(triggerDownload).toHaveBeenCalledTimes(2)
  })

  test('a click that gets the archive ready ends once it is saved', async () => {
    let saved = null
    vi.mocked(triggerDownload).mockReturnValueOnce(
      new Promise((resolve) => (saved = resolve))
    )
    let clicked = false

    click({ status: 200, data: archive }).then(() => (clicked = true))
    await flushPromises()

    expect(clicked).toBe(false)

    saved()
    await flushPromises()

    expect(clicked).toBe(true)
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

  test('shows why the archive cannot be handed out after the job', async () => {
    const wrapper = await startDownload()
    mockDownload().replyOnce(400, {
      error: 'ERROR_TEMPLATE_BLOCKED',
      detail: 'The template is blocked.',
    })

    await updateJob(store, 10, { state: 'finished' })

    expect(errorToasts()).toHaveLength(0)
    expect(wrapper.find('.toast__message').text()).toBe(
      'clientHandler.templateBlockedDescription'
    )
    expect(triggerDownload).not.toHaveBeenCalled()
  })

  test.each([
    [200, archive],
    [400, { error: 'ERROR_TEMPLATE_BLOCKED', detail: 'Blocked.' }],
  ])(
    'changes nothing when the archive answers %i after a logout',
    async (status, data) => {
      await startDownload()
      let reply = null
      mockDownload().reply(() => new Promise((resolve) => (reply = resolve)))

      // Ends once the archive is answered.
      const jobEnded = updateJob(store, 10, { state: 'finished' })
      await flushPromises()
      await store.dispatch('auth/forceLogoff')
      reply([status, data])
      await jobEnded

      expect(triggerDownload).not.toHaveBeenCalled()
      expect(downloadToasts()[0].data.state).toBeUndefined()
    }
  )

  test('adds one toast when a click gets a job that already has one', async () => {
    await startDownload()
    mockDownload().replyOnce(200, archive)

    // A repeated click got the job that runs already.
    await click({ status: 202, data: runningJob() })

    expect(downloadToasts()).toHaveLength(1)
    expect(store.getters['job/getAll']).toHaveLength(1)

    await updateJob(store, 10, { state: 'finished' })

    expect(triggerDownload).toHaveBeenCalledTimes(1)
  })

  test('replaces the ended toasts of the same download when it is clicked again', async () => {
    const other = { name: 'Roadmap', slug: 'roadmap-g7h8i9' }
    // Ready, failed, ready for the latest revision, and running for another
    // template.
    await click({ status: 200, data: archive })
    await click({ status: 202, data: runningJob({ id: 11 }) })
    await updateJob(store, 11, { state: 'failed', human_readable_error: 'x' })
    await click({ status: 200, data: archive }, { latest: true })
    await click(
      { status: 202, data: runningJob({ id: 13, slug: other.slug }) },
      { of: other }
    )

    await click({ status: 202, data: runningJob({ id: 14 }) })

    const shown = () =>
      downloadToasts().map(({ data }) => [data.slug, data.latest, data.jobId])
    // The newest toast comes first.
    const expected = [
      [template.slug, false, 14],
      [other.slug, false, 13],
      [template.slug, true, undefined],
    ]
    expect(shown()).toStrictEqual(expected)

    // A click that gets the running job of a template keeps its toast.
    await click(
      { status: 202, data: runningJob({ id: 13, slug: other.slug }) },
      { of: other }
    )

    expect(shown()).toStrictEqual(expected)
  })

  test('only shows the button for a download started before the page was loaded', async () => {
    // The pending jobs are fetched when the page loads, without their toast.
    await store.dispatch('job/forceCreate', runningJob({ latest: true }))
    mockDownload().replyOnce(200, archive)

    await updateJob(store, 10, { state: 'finished' })

    expect(downloadRequests()).toStrictEqual([
      [`/templates/${template.slug}/download/`, { latest: true }],
    ])
    expect(triggerDownload).not.toHaveBeenCalled()
    expect(downloadToasts()).toHaveLength(1)
    const t = vi.spyOn(testApp.nuxtApp.$i18n, 't')
    const wrapper = await mountToast()

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
    mockDownload().replyOnce(200, archive)
    vi.mocked(triggerDownload).mockRejectedValueOnce(new Error('403'))

    await updateJob(store, 10, { state: 'finished' })

    expect(errorToasts().map((toast) => toast.title)).toStrictEqual([
      'clientHandler.notCompletedTitle',
    ])
    expect(downloadToasts()).toHaveLength(1)
  })
})
