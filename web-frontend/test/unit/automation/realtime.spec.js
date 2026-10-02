import { registerRealtimeEvents } from '@baserow/modules/automation/realtime'

// Capture the handlers registered by registerRealtimeEvents so we can invoke
// individual realtime events directly.
const getHandlers = () => {
  const handlers = {}
  registerRealtimeEvents({
    registerEvent: (name, fn) => {
      handlers[name] = fn
    },
  })
  return handlers
}

const buildStore = ({ selectedWorkflow }) => ({
  getters: {
    'automationWorkflow/getSelected': selectedWorkflow,
  },
  dispatch: vi.fn(),
})

const runLifecycleEvents = [
  'automation_workflow_dispatch_started',
  'automation_workflow_dispatch_cancellation_requested',
  'automation_workflow_dispatch_done',
]

describe('automation realtime run lifecycle events', () => {
  const workflow = { id: 10 }

  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  test.each(runLifecycleEvents)(
    '%s refetches the history of the selected workflow',
    async (event) => {
      const handlers = getHandlers()
      const store = buildStore({ selectedWorkflow: workflow })

      handlers[event]({ store }, { workflow_id: workflow.id, history_id: 5 })

      await vi.advanceTimersByTimeAsync(1000)

      expect(store.dispatch).toHaveBeenCalledTimes(1)
      expect(store.dispatch).toHaveBeenCalledWith(
        'automationHistory/refreshWorkflowHistory',
        { workflowId: workflow.id }
      )
    }
  )

  test.each(runLifecycleEvents)(
    '%s ignores runs of a workflow that is not selected',
    async (event) => {
      const handlers = getHandlers()
      const store = buildStore({ selectedWorkflow: workflow })

      handlers[event]({ store }, { workflow_id: 999, history_id: 5 })

      await vi.advanceTimersByTimeAsync(1000)
      expect(store.dispatch).not.toHaveBeenCalled()
    }
  )

  test.each(runLifecycleEvents)(
    '%s is ignored when no workflow is selected',
    async (event) => {
      const handlers = getHandlers()
      const store = buildStore({ selectedWorkflow: undefined })

      handlers[event]({ store }, { workflow_id: workflow.id, history_id: 5 })

      await vi.advanceTimersByTimeAsync(1000)
      expect(store.dispatch).not.toHaveBeenCalled()
    }
  )

  test('groups started, cancellation and done events into one trailing refresh', async () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedWorkflow: workflow })
    for (let index = 0; index < 25; index++) {
      for (const event of runLifecycleEvents) {
        handlers[event]({ store }, { workflow_id: workflow.id })
      }
      await vi.advanceTimersByTimeAsync(20)
    }
    expect(store.dispatch).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(500)
    expect(store.dispatch).toHaveBeenCalledTimes(1)
    expect(store.dispatch).toHaveBeenCalledWith(
      'automationHistory/refreshWorkflowHistory',
      { workflowId: workflow.id }
    )
  })

  test('refreshes at least once a second during a continuous event stream', async () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedWorkflow: workflow })
    for (let second = 1; second <= 3; second++) {
      for (let index = 0; index < 10; index++) {
        handlers.automation_workflow_dispatch_done(
          { store },
          { workflow_id: workflow.id }
        )
        await vi.advanceTimersByTimeAsync(100)
      }
      expect(store.dispatch).toHaveBeenCalledTimes(second)
    }
  })

  test('does not let unrelated workflow events delay the selected history', async () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedWorkflow: workflow })
    handlers.automation_workflow_dispatch_done(
      { store },
      { workflow_id: workflow.id }
    )
    await vi.advanceTimersByTimeAsync(400)
    handlers.automation_workflow_dispatch_done({ store }, { workflow_id: 999 })
    await vi.advanceTimersByTimeAsync(100)
    expect(store.dispatch).toHaveBeenCalledTimes(1)
    expect(store.dispatch).toHaveBeenCalledWith(
      'automationHistory/refreshWorkflowHistory',
      { workflowId: workflow.id }
    )
  })

  test('drops a scheduled refresh if the selected workflow changes', async () => {
    const handlers = getHandlers()
    const store = buildStore({ selectedWorkflow: workflow })
    handlers.automation_workflow_dispatch_done(
      { store },
      { workflow_id: workflow.id }
    )
    store.getters['automationWorkflow/getSelected'] = { id: 999 }
    await vi.advanceTimersByTimeAsync(1000)
    expect(store.dispatch).not.toHaveBeenCalled()
  })
})
