<template>
  <div class="automation-app">
    <AutomationHeader :automation="automation" />
    <div class="layout__col-2-2 automation-app__content">
      <div class="automation-app__content-header">
        <div class="automation-app__title">{{ currentWorkflow.name }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'

export default {
  name: 'AutomationWorkflow',
  components: { AutomationHeader },
  provide() {
    return {
      workspace: this.workspace,
      automation: this.automation,
      currentWorkflow: this.currentWorkflow,
    }
  },
  layout: 'app',
  async asyncData({ store, params, error, $registry }) {
    const automationId = parseInt(params.automationId)
    const workflowId = parseInt(params.workflowId)

    const data = {}
    try {
      const automation = await store.dispatch(
        'application/selectById',
        automationId
      )
      const workspace = await store.dispatch(
        'workspace/selectById',
        automation.workspace.id
      )

      const workflow = store.getters['automationWorkflow/getById'](
        automation,
        workflowId
      )

      await store.dispatch('automationWorkflow/selectById', {
        automation,
        workflowId,
      })

      data.workspace = workspace
      data.automation = automation
      data.currentWorkflow = workflow
    } catch (e) {
      return error({
        statusCode: 404,
        message: 'Automation workflow not found.',
      })
    }
    return data
  },
}
</script>
