<template>
  <div class="automation-app">
    <AutomationHeader :automation="automation" />
    <div class="layout__col-2-2 automation-app__content">
      <div class="automation-app__content-header">
        <div class="automation-app__title">{{ automation.name }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import AutomationHeader from '@baserow/modules/automation/components/AutomationHeader'

export default {
  name: 'Automation',
  components: { AutomationHeader },
  layout: 'app',
  async asyncData({ store, params, error, $registry }) {
    const automationId = parseInt(params.automationId)
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
      data.workspace = workspace
      data.automation = automation
    } catch (e) {
      return error({ statusCode: 404, message: 'Automation not found.' })
    }
    return data
  },
}
</script>
