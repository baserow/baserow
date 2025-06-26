import { generateHash } from '@baserow/modules/core/utils/hashing'

export const registerRealtimeEvents = (realtime) => {
  // Workflow events
  realtime.registerEvent('automation_workflow_created', ({ store }, data) => {
    const automation = store.getters['application/get'](
      data.workflow.automation_id
    )
    store.dispatch('automationWorkflow/forceCreate', {
      automation,
      workflow: data.workflow,
    })
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

  realtime.registerEvent(
    'automation_workflows_reordered',
    ({ store, app }, data) => {
      const automation = store.getters['application/getAll'].find(
        (application) => generateHash(application.id) === data.automation_id
      )
      if (automation !== undefined) {
        store.commit('automationWorkflow/ORDER_WORKFLOWS', {
          automation,
          order: data.order,
          isHashed: true,
        })
      }
    }
  )
}
