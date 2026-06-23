<template>
  <form @submit.prevent>
    <FormGroup
      class="margin-bottom-2"
      :label="$t('coreStartWorkflowServiceForm.workflow')"
      :helper-text="$t('coreStartWorkflowServiceForm.workflowHelperText')"
      required
      small-label
    >
      <Dropdown
        v-model="values.workflow_id"
        size="large"
        show-search
        fixed-items
      >
        <DropdownSection
          v-for="automation in automations"
          :key="automation.id"
          :title="automation.name"
        >
          <DropdownItem
            v-for="workflow in automation.workflows"
            :key="workflow.id"
            :name="workflow.name"
            :value="workflow.id"
            :indented="true"
          />
        </DropdownSection>
      </Dropdown>
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { useVuelidate } from '@vuelidate/core'

export default {
  name: 'CoreStartWorkflowServiceForm',
  mixins: [form],
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: ['workflow_id'],
      values: {
        workflow_id: null,
      },
    }
  },
  computed: {
    automations() {
      const workspace = this.$store.getters['workspace/getSelected']
      if (!workspace.id) {
        return []
      }
      return this.$store.getters['application/getAllOfWorkspace'](workspace)
        .filter(
          (application) =>
            application.type === 'automation' &&
            this.getWorkflows(application).some(
              (workflow) => workflow.immediate_dispatch
            )
        )
        .map((automation) => ({
          ...automation,
          workflows: this.getWorkflows(automation).filter(
            (workflow) => workflow.immediate_dispatch
          ),
        }))
        .sort((a, b) => a.order - b.order)
    },
  },
  methods: {
    getWorkflows(automation) {
      return this.$store.getters['automationWorkflow/getOrderedWorkflows'](
        automation
      )
    },
  },
  validations() {
    return {
      values: {
        workflow_id: {},
      },
    }
  },
}
</script>
