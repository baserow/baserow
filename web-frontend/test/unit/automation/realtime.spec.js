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

  test.each(runLifecycleEvents)(
    '%s refetches the history of the selected workflow',
    (event) => {
      const handlers = getHandlers()
      const store = buildStore({ selectedWorkflow: workflow })

      handlers[event]({ store }, { workflow_id: workflow.id, history_id: 5 })

      expect(store.dispatch).toHaveBeenCalledTimes(1)
      expect(store.dispatch).toHaveBeenCalledWith(
        'automationHistory/fetchWorkflowHistory',
        { workflowId: workflow.id }
      )
    }
  )

  test.each(runLifecycleEvents)(
    '%s ignores runs of a workflow that is not selected',
    (event) => {
      const handlers = getHandlers()
      const store = buildStore({ selectedWorkflow: workflow })

      handlers[event]({ store }, { workflow_id: 999, history_id: 5 })

      expect(store.dispatch).not.toHaveBeenCalled()
    }
  )

  test.each(runLifecycleEvents)(
    '%s is ignored when no workflow is selected',
    (event) => {
      const handlers = getHandlers()
      const store = buildStore({ selectedWorkflow: undefined })

      handlers[event]({ store }, { workflow_id: workflow.id, history_id: 5 })

      expect(store.dispatch).not.toHaveBeenCalled()
    }
  )
})
