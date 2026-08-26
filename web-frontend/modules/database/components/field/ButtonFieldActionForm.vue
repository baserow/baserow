<template>
  <component
    :is="actionType.form"
    ref="form"
    :key="action.type"
    v-bind="actionType.getFormProps({ workflowAction: action, database })"
    :default-values="action"
    @values-changed="$emit('values-changed', $event)"
  />
</template>

<script>
import { computed } from 'vue'

/**
 * One action's form, with a formula context of its own. The data explorer
 * offers an action only what precedes it in the list, so each form needs to
 * know which action it belongs to, and `provide` is per component rather than
 * per loop iteration.
 */
export default {
  name: 'ButtonFieldActionForm',
  inject: {
    parentFormulaContext: { from: 'databaseFormulaContext', default: null },
  },
  provide() {
    return {
      databaseFormulaContext: computed(() => ({
        ...(this.parentFormulaContext || {}),
        workflowAction: this.action,
      })),
    }
  },
  props: {
    action: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  emits: ['values-changed'],
  computed: {
    actionType() {
      return this.$registry.get('databaseWorkflowActionType', this.action.type)
    },
  },
  methods: {
    /** Whether the action's own form accepts what it holds. */
    isValid() {
      return this.$refs.form?.isFormValid?.(true) ?? true
    },
  },
}
</script>
