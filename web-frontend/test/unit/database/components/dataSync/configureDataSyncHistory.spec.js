import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import ConfigureDataSyncHistory from '@baserow/modules/database/components/dataSync/ConfigureDataSyncHistory'
import { createSyncJob } from '@baserow/test/unit/database/components/dataSync/helpers'

describe('ConfigureDataSyncHistory', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const database = { id: 10, workspace: { id: 1 } }
  const table = { id: 20, name: 'Synced', data_sync: { id: 42 } }

  test('renders running, failed and finished runs', async () => {
    mockServer.fakeJobs({
      jobs: [
        createSyncJob({ id: 3, state: 'started', progress_percentage: 40 }),
        createSyncJob({
          id: 2,
          state: 'failed',
          triggered_by: 'periodic',
          user_name: 'Periodic user',
          human_readable_error: 'The sync failed badly.',
        }),
        createSyncJob({ id: 1, state: 'finished' }),
      ],
    })

    const wrapper = await testApp.mount(ConfigureDataSyncHistory, {
      propsData: { database, table },
    })
    await flushPromises()

    const items = wrapper.findAll('.data-sync-runs__item')
    expect(items).toHaveLength(3)

    expect(items.at(0).html()).toContain('job.stateStarted')
    expect(items.at(0).find('.progress-bar').exists()).toBe(false)
    expect(items.at(0).find('.data-sync-runs__duration').text()).toBe('40%')

    expect(items.at(1).html()).toContain('job.stateFailed')
    expect(items.at(1).html()).toContain('dataSyncRuns.triggerPeriodic')
    expect(items.at(1).html()).toContain('dataSyncRuns.byUser')

    // Error details are exposed through an accessible disclosure button.
    const errorToggle = items.at(1).find('.data-sync-runs__head')
    expect(errorToggle.element.tagName).toBe('BUTTON')
    expect(errorToggle.attributes('type')).toBe('button')
    expect(errorToggle.attributes('aria-expanded')).toBe('false')
    expect(items.at(1).find('.data-sync-runs__error').exists()).toBe(false)
    await errorToggle.trigger('click')
    expect(errorToggle.attributes('aria-expanded')).toBe('true')
    expect(items.at(1).find('.data-sync-runs__error').text()).toBe(
      'The sync failed badly.'
    )

    expect(items.at(2).html()).toContain('job.stateFinished')
    expect(items.at(2).html()).toContain('dataSyncRuns.triggerManual')
    expect(items.at(2).find('.data-sync-runs__head').element.tagName).toBe(
      'DIV'
    )
  })

  test('seeds unfinished jobs into the job store', async () => {
    mockServer.fakeJobs({
      jobs: [
        createSyncJob({ id: 1, state: 'started', progress_percentage: 40 }),
        createSyncJob({ id: 3, state: 'finished' }),
      ],
    })

    await testApp.mount(ConfigureDataSyncHistory, {
      propsData: { database, table },
    })
    await flushPromises()

    const storeJobIds = testApp.store.getters['job/getAll'].map((job) => job.id)
    expect(storeJobIds).toContain(1)
    expect(storeJobIds).not.toContain(3)
  })

  test('shows the empty state when there are no runs', async () => {
    mockServer.fakeJobs({ jobs: [] })

    const wrapper = await testApp.mount(ConfigureDataSyncHistory, {
      propsData: { database, table },
    })
    await flushPromises()

    expect(wrapper.html()).toContain('dataSyncRuns.noRuns')
  })

  test('paginates when there are more runs than the page size', async () => {
    mockServer.fakeJobs({
      jobs: Array.from({ length: 10 }, (_, index) =>
        createSyncJob({ id: 100 - index, state: 'finished' })
      ),
      count: 25,
    })

    const wrapper = await testApp.mount(ConfigureDataSyncHistory, {
      propsData: { database, table },
    })
    await flushPromises()

    expect(wrapper.findAll('.data-sync-runs__item')).toHaveLength(10)
    expect(wrapper.find('.paginator').exists()).toBe(true)
  })

  test('hides the paginator when everything fits one page', async () => {
    mockServer.fakeJobs({
      jobs: [createSyncJob({ id: 1, state: 'finished' })],
      count: 1,
    })

    const wrapper = await testApp.mount(ConfigureDataSyncHistory, {
      propsData: { database, table },
    })
    await flushPromises()

    expect(wrapper.find('.paginator').exists()).toBe(false)
  })

  test('shows an error when the runs cannot be loaded', async () => {
    testApp.dontFailOnErrorResponses()
    mockServer.mock
      .onGet('jobs/')
      .reply(400, { error: 'ERROR_SOMETHING', detail: '' })

    const wrapper = await testApp.mount(ConfigureDataSyncHistory, {
      propsData: { database, table },
    })
    await flushPromises()

    expect(wrapper.find('.alert').exists()).toBe(true)
    expect(wrapper.find('.data-sync-runs').exists()).toBe(false)
  })

  test('hides a stale loading error after a successful retry', async () => {
    testApp.dontFailOnErrorResponses()
    const firstPage = Array.from({ length: 10 }, (_, index) =>
      createSyncJob({ id: 100 - index, state: 'finished' })
    )
    mockServer.mock.onGet('jobs/').replyOnce(200, {
      jobs: firstPage,
      count: 20,
    })
    mockServer.mock
      .onGet('jobs/')
      .replyOnce(400, { error: 'ERROR_SOMETHING', detail: '' })
    mockServer.mock.onGet('jobs/').replyOnce(200, {
      jobs: [createSyncJob({ id: 1, state: 'finished' })],
      count: 20,
    })

    const wrapper = await testApp.mount(ConfigureDataSyncHistory, {
      propsData: { database, table },
    })
    await flushPromises()

    const nextPageButton = () => wrapper.findAll('.paginator__button').at(1)
    await nextPageButton().trigger('click')
    await flushPromises()
    expect(wrapper.find('.alert').exists()).toBe(true)

    await nextPageButton().trigger('click')
    await flushPromises()
    expect(wrapper.find('.alert').exists()).toBe(false)
    expect(wrapper.findAll('.data-sync-runs__item')).toHaveLength(1)
  })
})
