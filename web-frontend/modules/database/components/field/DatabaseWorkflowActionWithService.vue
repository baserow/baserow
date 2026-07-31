<template>
  <component
    :is="serviceType.formComponent"
    :application="database"
    :service="defaultValues.service"
    :service-type="serviceType"
    :enable-integration-picker="false"
    :databases="workspaceDatabases"
    :default-values="defaultValues.service"
    @values-changed="values.service = { ...defaultValues.service, ...$event }"
  />
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

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
    /**
     * A button field has no integration to source a table list from, so the
     * choice is every database in the field's own workspace. The field's own
     * database is included on purpose: a button acting on its own table is
     * legitimate.
     */
    workspaceDatabases() {
      return this.$store.getters['application/getAllOfWorkspace'](
        this.database.workspace
      ).filter(
        (application) => application.type === DatabaseApplicationType.getType()
      )
    },
  },
}
</script>
