import { TestApp } from '@baserow/test/helpers/testApp'

const WORKFLOW_ID = 3
const HISTORY_ID = 11
const CANCEL_URL = `automation/workflow_histories/${HISTORY_ID}/cancel/`
const HISTORY_URL = `automation/workflows/${WORKFLOW_ID}/history/`

const history = (extra = {}) => ({
  id: HISTORY_ID,
  status: 'started',
  cancellation_requested_on: null,
  ...extra,
})

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

  const cancelRun = () =>
    store.dispatch('automationHistory/cancelWorkflowRun', {
      workflowId: WORKFLOW_ID,
      workflowHistoryId: HISTORY_ID,
    })

  test('cancelWorkflowRun posts the cancellation and refetches the history', async () => {
    const cancelling = history({
      cancellation_requested_on: '2026-09-15T10:00:05Z',
    })
    testApp.mock.onPost(CANCEL_URL).reply(200, cancelling)
    testApp.mock.onGet(HISTORY_URL).reply(200, [cancelling])

    await cancelRun()

    expect(testApp.mock.history.post).toHaveLength(1)
    expect(testApp.mock.history.get).toHaveLength(1)
    expect(store.getters['automationHistory/getWorkflowHistory']()).toEqual([
      cancelling,
    ])
  })

  test('cancelWorkflowRun refetches the history even when the run is not running anymore', async () => {
    testApp.failTestOnErrorResponse = false
    const finished = history({ status: 'success' })
    testApp.mock.onPost(CANCEL_URL).reply(400, {
      error: 'ERROR_AUTOMATION_WORKFLOW_HISTORY_NOT_RUNNING',
      detail: 'The automation workflow history is not running anymore.',
    })
    testApp.mock.onGet(HISTORY_URL).reply(200, [finished])

    let caught = null
    try {
      await cancelRun()
    } catch (error) {
      caught = error
    }

    expect(caught?.handler?.code).toBe(
      'ERROR_AUTOMATION_WORKFLOW_HISTORY_NOT_RUNNING'
    )
    expect(testApp.mock.history.get).toHaveLength(1)
    expect(store.getters['automationHistory/getWorkflowHistory']()).toEqual([
      finished,
    ])
  })
})
