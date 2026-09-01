<template>
  <div>
    <LocalBaserowIntegrationPicker
      v-if="workflowActionType.picksIntegration"
      v-model="integrationId"
      :application="builder"
    />
    <!-- The buffered values are kept, or a freshly picked integration is lost:
         the form below no longer emits `integration_id`. -->
    <component
      :is="serviceType.formComponent"
      v-if="!workflowActionType.picksIntegration || integrationId"
      :application="builder"
      :service="defaultValues.service"
      :service-type="serviceType"
      :loading="workflowActionLoading"
      :databases="databases"
      :default-values="defaultValues.service"
      @values-changed="bufferServiceChange($event)"
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
      // The service changes the user has made but not yet had saved,
      // accumulated from the wrapped form's `values-changed` events. The form
      // only emits editable fields, so this never carries the read-only,
      // backend-computed ones (`schema`, sample data, …); those always come
      // fresh from `workflowAction.service` when we rebuild `values.service`.
      pendingServiceChanges: {},
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
        this.bufferServiceChange({ integration_id: newValue })
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
  methods: {
    /**
     * Records an editable service change and rebuilds `values.service` from the
     * latest server service plus the accumulated changes. Buffering the changes
     * keeps a follow-up edit (or a freshly picked integration) that lands before
     * the debounced save completes, while the read-only fields are always taken
     * fresh from `workflowAction.service` instead of a stale buffered copy.
     */
    bufferServiceChange(changes) {
      this.pendingServiceChanges = {
        ...this.pendingServiceChanges,
        ...changes,
      }
      this.values.service = {
        ...this.workflowAction?.service,
        ...this.pendingServiceChanges,
      }
    },
  },
}
</script>
