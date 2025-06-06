<template>
  <component
    :is="serviceType.formComponent"
    :application="builder"
    :workflow-action="workflowAction"
    :default-values="defaultValues.service"
    @values-changed="values.service = { ...workflowAction.service, ...$event }"
  >
  </component>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'WorkflowActionWithWithService',
  mixins: [form],
  inject: ['builder'],
  props: {
    workflowAction: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      allowedValues: ['service'],
      values: {
        service: {},
      },
    }
  },
  computed: {
    workflowActionType() {
      return this.$registry.get('workflowAction', this.workflowAction.type)
    },
    serviceType() {
      return this.workflowActionType.serviceType
    },
  },
}
</script>
