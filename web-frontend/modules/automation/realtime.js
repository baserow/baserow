import debounce from 'lodash/debounce'

export const registerRealtimeEvents = (realtime) => {
  // Workflow events
  realtime.registerEvent('automation_workflow_created', ({ store }, data) => {
    const automation = store.getters['application/get'](
      data.workflow.automation_id
    )
    if (automation !== undefined) {
      store.dispatch('automationWorkflow/forceCreate', {
        automation,
        workflow: data.workflow,
      })
    }
  })

  realtime.registerEvent('automation_workflow_deleted', ({ store }, data) => {
    const automation = store.getters['application/get'](data.automation_id)
    if (automation !== undefined) {
      const workflow = store.getters['automationWorkflow/getWorkflows'](
        automation
      ).find((w) => w.id === data.workflow_id)
      if (workflow !== undefined) {
        store.dispatch('automationWorkflow/forceDelete', {
          automation,
          workflow,
        })
      }
    }
  })

  realtime.registerEvent('automation_workflow_updated', ({ store }, data) => {
    const automation = store.getters['application/get'](
      data.workflow.automation_id
    )
    if (automation !== undefined) {
      const workflow = store.getters['automationWorkflow/getWorkflows'](
        automation
      ).find((w) => w.id === data.workflow.id)
      if (workflow !== undefined) {
        store.dispatch('automationWorkflow/forceUpdate', {
          automation,
          workflow,
          values: data.workflow,
        })
      }
    }
  })

  realtime.registerEvent('automation_workflow_published', ({ store }, data) => {
    const automation = store.getters['application/get'](
      data.workflow.automation_id
    )
    if (automation !== undefined) {
      const workflow = store.getters['automationWorkflow/getWorkflows'](
        automation
      ).find((w) => w.id === data.workflow.id)
      if (workflow !== undefined) {
        store.dispatch('automationWorkflow/forceUpdate', {
          automation,
          workflow,
          values: data.workflow,
        })
      }
    }
  })

  // Workflow node events
  realtime.registerEvent('automation_node_created', ({ store }, data) => {
    const workflow = store.getters['automationWorkflow/getSelected']
    if (workflow && workflow.id === data.node.workflow) {
      store.dispatch('automationWorkflowNode/forceCreate', {
        workflow,
        node: data.node,
      })
    }
  })

  realtime.registerEvent('automation_node_updated', ({ store }, data) => {
    const workflow = store.getters['automationWorkflow/getSelected']
    const node = data.node
    if (!workflow || !node) return
    if (workflow.id !== (node.workflow || node.workflow_id)) return

    const existing = store.getters['automationWorkflowNode/findById'](
      workflow,
      node.id
    )
    if (!existing) return

    // The event was too large for a websocket frame, so the server left the
    // sample data out and asks us to reload the node over HTTP instead.
    if (data.requires_refresh === true) {
      store.dispatch('automationWorkflowNode/refetch', {
        workflow,
        nodeId: node.id,
      })
      return
    }

    store.dispatch('automationWorkflowNode/forceUpdate', {
      workflow,
      node: existing,
      values: node,
      override: true,
      viaRealtime: true,
    })
  })

  realtime.registerEvent('automation_node_deleted', ({ store }, data) => {
    const workflow = store.getters['automationWorkflow/getSelected']
    const nodeId = data.node_id || data.node?.id
    const workflowId = data.workflow || data.workflow_id || data.node?.workflow
    if (!workflow || !nodeId) return
    if (workflowId && workflow.id !== workflowId) return

    store.dispatch('automationWorkflowNode/forceDelete', {
      workflow,
      nodeId,
    })
  })

  // Group run lifecycle bursts even when history requests complete quickly.
  // maxWait keeps the panel updating during a continuous stream of events.
  const refreshHistory = debounce(
    (store, workflowId) => {
      const selectedWorkflow = store.getters['automationWorkflow/getSelected']
      if (selectedWorkflow?.id === workflowId) {
        store.dispatch('automationHistory/refreshWorkflowHistory', {
          workflowId,
        })
      }
    },
    500,
    { maxWait: 1000 }
  )
  const refetchSelectedWorkflowHistory = ({ store }, data) => {
    const selectedWorkflow = store.getters['automationWorkflow/getSelected']
    if (selectedWorkflow?.id === data.workflow_id) {
      refreshHistory(store, data.workflow_id)
    }
  }

  for (const event of [
    'automation_workflow_dispatch_started',
    'automation_workflow_dispatch_cancellation_requested',
    'automation_workflow_dispatch_done',
  ]) {
    realtime.registerEvent(event, refetchSelectedWorkflowHistory)
  }

  // A node of a run still in progress started or stopped waiting. The run's
  // entry is unchanged, only its node rows are refetched, and only when the
  // panel already shows them. A run executes its nodes one after another, so
  // its events come in pairs at most: a resume is followed within
  // milliseconds by the suspend of the next wait. Several runs of the same
  // workflow do execute at once though (e.g. one per created row), each with
  // its own history id. Both cases are grouped into one refetch per run,
  // like the run lifecycle events above.
  const pendingHistoryIds = new Set()
  const refreshNodeHistories = debounce(
    (store, workflowId) => {
      const workflowHistoryIds = [...pendingHistoryIds]
      pendingHistoryIds.clear()
      const selectedWorkflow = store.getters['automationWorkflow/getSelected']
      if (selectedWorkflow?.id !== workflowId) return
      for (const workflowHistoryId of workflowHistoryIds) {
        store.dispatch('automationHistory/refreshNodeHistories', {
          workflowHistoryId,
        })
      }
    },
    500,
    { maxWait: 1000 }
  )
  realtime.registerEvent(
    'automation_workflow_history_updated',
    ({ store }, data) => {
      const selectedWorkflow = store.getters['automationWorkflow/getSelected']
      if (selectedWorkflow?.id === data.workflow_id) {
        pendingHistoryIds.add(data.history_id)
        refreshNodeHistories(store, data.workflow_id)
      }
    }
  )
}
