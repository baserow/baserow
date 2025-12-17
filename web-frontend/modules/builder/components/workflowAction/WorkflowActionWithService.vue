<template>
  <component
    :is="serviceType.formComponent"
    :application="builder"
    :service="defaultValues.service"
    :service-type="serviceType"
    :loading="workflowActionLoading"
    :default-values="defaultValues.service"
    @values-changed="values.service = { ...workflowAction.service, ...$event }"
  >
  </component>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'WorkflowActionWithService',
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
    workflowActionLoading() {
      return this.$store.getters['builderWorkflowAction/getLoading'](
        this.workflowAction
      )
    },
    workflowActionType() {
      return this.$registry.get('workflowAction', this.workflowAction.type)
    },
    serviceType() {
      return this.workflowActionType.serviceType
    },
  },
}
</script>
