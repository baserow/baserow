import flushPromises from 'flush-promises'

import { TestApp } from '@baserow/test/helpers/testApp'

const WORKFLOW_ID = 3
const HISTORY_ID = 11
const CANCEL_URL = `automation/workflow_histories/${HISTORY_ID}/cancel/`
const HISTORY_URL = `automation/workflows/${WORKFLOW_ID}/history/`
const REQUESTED_ON = '2026-09-15T10:00:05Z'

const history = (extra = {}) => ({
  id: HISTORY_ID,
  status: 'started',
  cancellation_requested_on: null,
  plugin_data: { premium: { some: 'value' } },
  ...extra,
})

// The list endpoint answers with a page of entries.
const page = (results) => ({
  count: results.length,
  next: null,
  previous: null,
  success_count: 0,
  fail_count: 0,
  results,
})

// A reply the test resolves itself, to make responses land in a chosen order.
const deferredReply = () => {
  let resolve = null
  const promise = new Promise((r) => {
    resolve = r
  })
  return {
    reply: () => promise,
    resolve: (status, data) => resolve([status, data]),
  }
}

describe('automation history store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const getHistory = () =>
    store.getters['automationHistory/getWorkflowHistory']()

  const fetchHistory = () =>
    store.dispatch('automationHistory/fetchWorkflowHistory', {
      workflowId: WORKFLOW_ID,
    })

  const cancelRun = () =>
    store.dispatch('automationHistory/cancelWorkflowRun', {
      workflowId: WORKFLOW_ID,
      workflowHistoryId: HISTORY_ID,
    })

  describe('fetchWorkflowHistory', () => {
    test('commits responses that land in the order they were started', async () => {
      const first = deferredReply()
      const second = deferredReply()
      testApp.mock.onGet(HISTORY_URL).replyOnce(first.reply)
      testApp.mock.onGet(HISTORY_URL).replyOnce(second.reply)

      const firstFetch = fetchHistory()
      const secondFetch = fetchHistory()

      first.resolve(200, page([history()]))
      await firstFetch
      expect(getHistory()).toEqual(page([history()]))

      second.resolve(200, page([history({ status: 'success' })]))
      await secondFetch
      expect(getHistory()).toEqual(page([history({ status: 'success' })]))
    })

    test('drops a response overtaken by a newer fetch', async () => {
      const first = deferredReply()
      const second = deferredReply()
      testApp.mock.onGet(HISTORY_URL).replyOnce(first.reply)
      testApp.mock.onGet(HISTORY_URL).replyOnce(second.reply)

      const firstFetch = fetchHistory()
      const secondFetch = fetchHistory()

      second.resolve(200, page([history({ status: 'success' })]))
      await secondFetch
      expect(getHistory()).toEqual(page([history({ status: 'success' })]))

      first.resolve(200, page([history()]))
      await firstFetch
      expect(getHistory()).toEqual(page([history({ status: 'success' })]))
    })
  })

  describe('cancelWorkflowRun', () => {
    test('applies the cancellation response right away, then the refetch', async () => {
      testApp.mock.onGet(HISTORY_URL).replyOnce(200, page([history()]))
      await fetchHistory()

      const cancelling = history({ cancellation_requested_on: REQUESTED_ON })
      // The cancel endpoint answers without the plugin data of the list.
      testApp.mock
        .onPost(CANCEL_URL)
        .reply(200, { ...cancelling, plugin_data: {} })
      const refetch = deferredReply()
      testApp.mock.onGet(HISTORY_URL).replyOnce(refetch.reply)

      const cancel = cancelRun()
      await flushPromises()

      expect(testApp.mock.history.post).toHaveLength(1)
      expect(testApp.mock.history.get).toHaveLength(2)
      // The entry shows as cancelling before the refetch has landed and keeps
      // its plugin data.
      expect(getHistory().results[0]).toEqual(cancelling)

      refetch.resolve(200, page([cancelling]))
      await cancel
      expect(getHistory()).toEqual(page([cancelling]))
    })

    test('is not undone by a fetch that was started before it', async () => {
      testApp.mock.onGet(HISTORY_URL).replyOnce(200, page([history()]))
      await fetchHistory()

      // This fetch read the run before the cancellation was recorded.
      const stale = deferredReply()
      testApp.mock.onGet(HISTORY_URL).replyOnce(stale.reply)
      const staleFetch = fetchHistory()

      const cancelling = history({ cancellation_requested_on: REQUESTED_ON })
      testApp.mock
        .onPost(CANCEL_URL)
        .reply(200, { ...cancelling, plugin_data: {} })
      testApp.mock.onGet(HISTORY_URL).replyOnce(200, page([cancelling]))
      await cancelRun()
      expect(getHistory()).toEqual(page([cancelling]))

      stale.resolve(200, page([history()]))
      await staleFetch
      expect(getHistory()).toEqual(page([cancelling]))
    })

    test('refetches even when the run is not in the loaded page', async () => {
      const cancelling = history({ cancellation_requested_on: REQUESTED_ON })
      testApp.mock
        .onPost(CANCEL_URL)
        .reply(200, { ...cancelling, plugin_data: {} })
      testApp.mock.onGet(HISTORY_URL).replyOnce(200, page([cancelling]))

      await cancelRun()

      expect(getHistory()).toEqual(page([cancelling]))
    })

    // The backend refuses when the run resolved first, or when somebody else
    // already requested the cancellation. Either way the refetch shows what
    // the run's entry looks like now.
    test.each([
      [
        'ERROR_AUTOMATION_WORKFLOW_HISTORY_NOT_RUNNING',
        history({ status: 'success' }),
      ],
      [
        'ERROR_AUTOMATION_WORKFLOW_HISTORY_CANCELLATION_ALREADY_REQUESTED',
        history({ cancellation_requested_on: REQUESTED_ON }),
      ],
    ])('refetches even when the backend answers %s', async (code, current) => {
      testApp.dontFailOnErrorResponses()
      testApp.mock.onGet(HISTORY_URL).replyOnce(200, page([history()]))
      await fetchHistory()

      testApp.mock.onPost(CANCEL_URL).reply(400, { error: code, detail: '' })
      testApp.mock.onGet(HISTORY_URL).replyOnce(200, page([current]))

      let caught = null
      try {
        await cancelRun()
      } catch (error) {
        caught = error
      }

      expect(caught?.handler?.code).toBe(code)
      expect(testApp.mock.history.get).toHaveLength(2)
      expect(getHistory()).toEqual(page([current]))
    })
  })
})
