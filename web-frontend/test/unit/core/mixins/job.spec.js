import { vi } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'
import jobMixin from '@baserow/modules/core/mixins/job'

describe('job mixin', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('onJobCancelFailed is called when the cancellation request fails', async () => {
    testApp.dontFailOnErrorResponses()
    const onJobCancelFailed = vi.fn()
    const showError = vi.fn()
    const TestComponent = {
      template: '<div></div>',
      mixins: [jobMixin],
      methods: { onJobCancelFailed, showError },
    }

    const wrapper = await testApp.mount(TestComponent, {})
    wrapper.vm.job = await testApp.store.dispatch('job/create', {
      id: 1,
      type: 'export_applications',
      state: 'started',
      progress_percentage: 10,
    })
    testApp.mockServer.mock
      .onPost('/jobs/1/cancel/')
      .reply(400, { error: 'ERROR_SOMETHING', detail: '' })

    await wrapper.vm.cancelJob()

    expect(showError).toHaveBeenCalled()
    expect(onJobCancelFailed).toHaveBeenCalled()
  })
})
