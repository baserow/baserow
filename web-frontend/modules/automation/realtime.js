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

  // Run lifecycle events. The history panel only shows the selected
  // workflow, so its entries are refetched when one of its runs starts,
  // gets a cancellation request or resolves.
  const refetchSelectedWorkflowHistory = ({ store }, data) => {
    const selectedWorkflow = store.getters['automationWorkflow/getSelected']
    if (selectedWorkflow && selectedWorkflow.id === data.workflow_id) {
      store.dispatch('automationHistory/refreshWorkflowHistory', {
        workflowId: data.workflow_id,
      })
    }
  }

  for (const event of [
    'automation_workflow_dispatch_started',
    'automation_workflow_dispatch_cancellation_requested',
    'automation_workflow_dispatch_done',
  ]) {
    realtime.registerEvent(event, refetchSelectedWorkflowHistory)
  }
}
