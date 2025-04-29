<template>
  <Modal>
    <h2 class="box__title">
      {{ $t('createAutomationWorkflowModal.header') }}
    </h2>
    <AutomationWorkflowSettingsForm
      ref="automationWorkflowForm"
      :automation="automation"
      is-creation
      @submitted="addWorkflow"
    >
      <div class="actions actions--right">
        <Button size="large" :loading="loading">
          {{ $t('createAutomationWorkflowModal.submit') }}
        </Button>
      </div>
    </AutomationWorkflowSettingsForm>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import AutomationWorkflowSettingsForm from '@baserow/modules/automation/components/workflow/settings/AutomationWorkflowSettingsForm'

export default {
  name: 'CreateAutomationWorkflowModal',
  components: { AutomationWorkflowSettingsForm },
  mixins: [modal],
  provide() {
    return {
      currentPage: null,
      automation: this.automation,
      workspace: this.workspace,
    }
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    automation: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async addWorkflow({ name }) {
      this.loading = true
      try {
        const workflow = await this.$store.dispatch(
          'automationWorkflow/create',
          {
            automation: this.automation,
            name,
          }
        )
        this.$refs.automationWorkflowForm.v$.$reset()
        this.hide()
        this.$router.push(
          {
            name: 'automation-workflow',
            params: {
              automationId: this.automation.id,
              workflowId: workflow.id,
            },
          },
          null,
          () => {}
        )
      } catch (error) {
        notifyIf(error, 'application')
      }
      this.loading = false
    },
  },
}
</script>
