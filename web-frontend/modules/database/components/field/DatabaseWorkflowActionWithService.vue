<template>
  <component
    :is="serviceType.formComponent"
    :application="database"
    :service="defaultValues.service"
    :service-type="serviceType"
    :default-values="defaultValues.service"
    @values-changed="values.service = { ...defaultValues.service, ...$event }"
  />
</template>

<script>
import form from '@baserow/modules/core/mixins/form'

export default {
  name: 'DatabaseWorkflowActionWithService',
  mixins: [form],
  props: {
    workflowAction: {
      type: Object,
      required: true,
    },
    database: {
      type: Object,
      required: true,
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
      return this.$registry.get(
        'databaseWorkflowActionType',
        this.workflowAction.type
      )
    },
    serviceType() {
      return this.workflowActionType.serviceType
    },
  },
}
</script>
