<template>
  <FormGroup
    :label="$t('localBaserowServiceForm.integrationDropdownLabel')"
    small-label
    required
    class="margin-bottom-2"
  >
    <IntegrationDropdown
      :model-value="modelValue"
      :application="application"
      :integrations="integrations"
      :integration-type="integrationType"
      @update:model-value="$emit('update:modelValue', $event)"
    />
  </FormGroup>
</template>

<script>
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/localBaserow/integrationTypes'

/**
 * Chooses the Local Baserow integration a service reaches its tables through.
 * Only the builder and automation wrappers render it, a button field has no
 * integration to pick.
 */
export default {
  name: 'LocalBaserowIntegrationPicker',
  components: { IntegrationDropdown },
  props: {
    application: {
      type: Object,
      required: true,
    },
    modelValue: {
      type: Number,
      required: false,
      default: null,
    },
  },
  emits: ['update:modelValue'],
  computed: {
    integrationType() {
      return this.$registry.get(
        'integration',
        LocalBaserowIntegrationType.getType()
      )
    },
    integrations() {
      return this.$store.getters['integration/getIntegrations'](
        this.application
      ).filter(
        (integration) =>
          integration.type === LocalBaserowIntegrationType.getType()
      )
    },
  },
}
</script>
