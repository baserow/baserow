import { isApplicationBundleLoaded } from '@baserow/modules/core/utils/applicationBundles'
import { populateAutomationWorkflow } from '@baserow/modules/automation/utils/populateAutomationWorkflow'

/** Keep unopened automation lists current while their editor and stores stay deferred. */
export default function register(app) {
  const { $realtime: realtime, $store: store } = app
  for (const event of [
    'automation_workflow_created',
    'automation_workflow_updated',
    'automation_workflow_published',
    'automation_workflow_deleted',
  ]) {
    realtime.registerEvent(event, (_, data) => {
      if (isApplicationBundleLoaded(app, 'automation')) return
      const automation = store.getters['application/get'](
        data.workflow?.automation_id ?? data.automation_id
      )
      if (!automation) return
      const id = data.workflow?.id ?? data.workflow_id
      const workflows = automation.workflows.filter(
        (workflow) => workflow.id !== id
      )
      if (event !== 'automation_workflow_deleted') {
        const previous = automation.workflows.find(
          (workflow) => workflow.id === id
        )
        workflows.push(
          previous
            ? { ...previous, ...data.workflow }
            : populateAutomationWorkflow(data.workflow)
        )
      }
      store.commit('application/UPDATE_ITEM', {
        id: automation.id,
        values: { workflows },
        viaRealtime: true,
      })
    })
  }
}
