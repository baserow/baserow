import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import SyncTableModal from '@baserow/modules/database/components/dataSync/SyncTableModal'
import { createSyncJob } from '@baserow/test/unit/database/components/dataSync/helpers'

describe('SyncTableModal', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const table = { id: 20, name: 'Synced', data_sync: { id: 42 } }

  test('shows previous runs and attaches to an in-flight one', async () => {
    mockServer.fakeJobs({
      jobs: [
        createSyncJob({
          id: 7,
          state: 'started',
          progress_percentage: 60,
          triggered_by: 'periodic',
          user_name: 'Periodic user',
        }),
        createSyncJob({ id: 6, state: 'finished' }),
      ],
    })

    const wrapper = await testApp.mount(SyncTableModal, {
      propsData: { table },
    })
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.html()).toContain('dataSyncRuns.previousRuns')
    expect(wrapper.findAll('.data-sync-runs__item')).toHaveLength(2)
    expect(wrapper.find('button[disabled]').exists()).toBe(true)
    expect(testApp.store.getters['job/get'](7)).toBeTruthy()
  })

  test('stays idle when no sync run is in flight', async () => {
    mockServer.fakeJobs({
      jobs: [createSyncJob({ id: 6, state: 'finished' })],
    })

    const wrapper = await testApp.mount(SyncTableModal, {
      propsData: { table },
    })
    await wrapper.vm.show()
    await flushPromises()

    expect(wrapper.findAll('.data-sync-runs__item')).toHaveLength(1)
    expect(wrapper.find('button[disabled]').exists()).toBe(false)
  })
})
