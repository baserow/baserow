<template>
  <div>
    <LocalBaserowIntegrationPicker
      v-model="values.integration_id"
      :application="application"
    />
    <component
      :is="serviceType.formComponent"
      v-if="values.integration_id"
      v-bind="$attrs"
      :application="application"
      :service="service"
      :service-type="serviceType"
      :databases="databases"
      :default-values="defaultValues"
      @values-changed="$emit('values-changed', $event)"
    />
  </div>
</template>

<script>
import LocalBaserowIntegrationPicker from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowIntegrationPicker'
import { databasesOfIntegration } from '@baserow/modules/integrations/localBaserow/utils/integration'
import form from '@baserow/modules/core/mixins/form'

/**
 * An automation node chooses its own integration; the wrapped form only picks a
 * table, so it waits for one, like the builder's data source form.
 */
export default {
  name: 'LocalBaserowNodeServiceForm',
  components: { LocalBaserowIntegrationPicker },
  mixins: [form],
  // What the side panel passes is for the wrapped form, not for the element
  // this one renders.
  inheritAttrs: false,
  props: {
    application: {
      type: Object,
      required: true,
    },
    service: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    serviceType: {
      type: Object,
      required: true,
    },
  },
  emits: ['values-changed'],
  data() {
    return {
      allowedValues: ['integration_id'],
      values: { integration_id: null },
    }
  },
  computed: {
    databases() {
      return databasesOfIntegration(
        this.$store,
        this.application,
        this.values.integration_id
      )
    },
  },
}
</script>
