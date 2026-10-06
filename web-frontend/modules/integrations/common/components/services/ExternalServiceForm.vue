<template>
  <form @submit.prevent>
    <Alert v-if="!values.integration_id" type="info-neutral">
      <p>
        {{
          $t('externalServiceForm.alertMessage', {
            integration: integrationType.name,
          })
        }}
      </p>
    </Alert>
    <FormGroup
      :label="$t('externalServiceForm.integrationLabel')"
      small-label
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
        :allow-editing="editableFromHere"
      />
    </FormGroup>
    <FormGroup
      v-for="field in fields"
      :key="field.name"
      class="margin-bottom-2"
      :label="$t(field.label)"
      :helper-text="field.help ? $t(field.help) : ''"
      :required="field.required"
      :error-message="getFirstErrorMessage(field.name)"
      small-label
    >
      <InjectedFormulaInput
        v-if="field.type === 'formula'"
        v-model="values[field.name]"
        :placeholder="field.placeholder ? $t(field.placeholder) : ''"
      />
      <FormInput
        v-else
        v-model="v$.values[field.name].$model"
        type="number"
        :min="field.min"
        :max="field.max"
      />
    </FormGroup>
  </form>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { helpers, integer, maxValue, minValue } from '@vuelidate/validators'
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown.vue'

/**
 * Renders the fields a third-party action declares in its service type, so
 * the Google, Microsoft and Jira actions share one form.
 */
export default {
  name: 'ExternalServiceForm',
  components: { IntegrationDropdown, InjectedFormulaInput },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
    serviceType: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    const fields = this.serviceType.formFields
    const values = { integration_id: null }
    for (const field of fields) {
      values[field.name] = field.type === 'formula' ? {} : null
    }
    return {
      allowedValues: ['integration_id', ...fields.map((field) => field.name)],
      values,
    }
  },
  computed: {
    fields() {
      return this.serviceType.formFields
    },
    /**
     * Without a settings page an integration can only be repaired, or an
     * account connected, from the picker.
     */
    editableFromHere() {
      return !this.$registry.get('application', this.application.type)
        .hasIntegrationSettingsPage
    },
    integrationType() {
      return this.serviceType.integrationType
    },
    integrations() {
      const allIntegrations = this.$store.getters[
        'integration/getIntegrations'
      ](this.application)
      return allIntegrations.filter(
        (integration) => integration.type === this.integrationType.type
      )
    },
  },
  validations() {
    const values = {}
    for (const field of this.fields) {
      if (field.type === 'integer') {
        values[field.name] = {
          integer: helpers.withMessage(this.$t('error.integerField'), integer),
          minValue: helpers.withMessage(
            this.$t('error.minValueField', { min: field.min }),
            minValue(field.min)
          ),
          maxValue: helpers.withMessage(
            this.$t('error.maxValueField', { max: field.max }),
            maxValue(field.max)
          ),
        }
      }
    }
    return { values }
  },
}
</script>
