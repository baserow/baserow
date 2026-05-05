<template>
  <Modal ref="modal">
    <WorkflowGeneralSettings
      :automation="automation"
      :workflow="workflow"
      :default-values="workflow"
    />
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import WorkflowGeneralSettings from '@baserow/modules/automation/components/settings/WorkflowGeneralSettings'

export default {
  name: 'WorkflowSettingsModal',
  components: { WorkflowGeneralSettings },
  mixins: [modal],
  props: {
    automation: {
      type: Object,
      required: true,
    },
    workflow: {
      type: Object,
      required: true,
    },
  },
}
</script>
