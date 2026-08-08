<template>
  <div>
    <LocalBaserowIntegrationPicker
      v-if="workflowActionType.picksIntegration"
      v-model="integrationId"
      :application="builder"
    />
    <component
      :is="serviceType.formComponent"
      v-if="!workflowActionType.picksIntegration || integrationId"
      :application="builder"
      :service="defaultValues.service"
      :service-type="serviceType"
      :loading="workflowActionLoading"
      :databases="databases"
      :default-values="defaultValues.service"
      @values-changed="
        values.service = { ...workflowAction.service, ...$event }
      "
    >
    </component>
  </div>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import LocalBaserowIntegrationPicker from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowIntegrationPicker'
import { databasesOfIntegration } from '@baserow/modules/integrations/localBaserow/utils/integration'

export default {
  name: 'WorkflowActionWithService',
  components: { LocalBaserowIntegrationPicker },
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
    /**
     * The integration is stored on the service, alongside everything else the
     * form emits.
     */
    integrationId: {
      get() {
        return (
          this.values.service?.integration_id ??
          this.defaultValues.service?.integration_id ??
          null
        )
      },
      set(newValue) {
        this.values.service = {
          ...this.workflowAction?.service,
          ...this.values.service,
          integration_id: newValue,
        }
      },
    },
    databases() {
      return databasesOfIntegration(
        this.$store,
        this.builder,
        this.integrationId
      )
    },
  },
}
</script>
