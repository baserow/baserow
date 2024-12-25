<template>
  <div class="data-source-form">
    <div class="data-source-form__header">
      <div class="data-source-form__header-form">
        <FormGroup
          :label="$t('dataSourceForm.actionLabel')"
          small-label
          required
          :error-message="typeError"
        >
          <Dropdown
            v-model="computedType"
            fixed-items
            class="data-source-form__type-dropdown"
            :placeholder="$t('dataSourceForm.servicePlaceholder')"
          >
            <template
              v-for="[, serviceTypesForDrop] in serviceTypesPerIntegration"
            >
              <DropdownItem
                v-for="serviceTypeForDrop in serviceTypesForDrop"
                :key="serviceTypeForDrop.getType()"
                :name="serviceTypeForDrop.name"
                :value="serviceTypeForDrop.getType()"
                :image="serviceTypeForDrop.integrationType.image"
              >
              </DropdownItem>
            </template>
          </Dropdown>
        </FormGroup>
        <FormGroup
          :label="$t('dataSourceForm.integrationLabel')"
          small-label
          required
          :error-message="integrationError"
        >
          <IntegrationDropdown
            v-model="values.integration_id"
            class="data-source-form__integration-dropdown"
            :application="builder"
            :integrations="integrations"
            :disabled="!values.type"
            :integration-type="serviceType?.integrationType"
          />
        </FormGroup>
        <FormGroup
          :label="$t('dataSourceForm.nameLabel')"
          small-label
          required
          :error-message="nameError"
        >
          <FormInput
            v-model="values.name"
            class="data-source-form__name-input"
            :placeholder="$t('dataSourceForm.namePlaceholder')"
            @blur="$v.values.name.$touch()"
          />
        </FormGroup>
      </div>
    </div>
    <template v-if="!create && integration">
      <component
        :is="serviceType.formComponent"
        ref="subForm"
        :builder="builder"
        :data-source="dataSource"
        :default-values="defaultValues"
        :context-data="integration.context_data"
        @values-changed="emitChange($event)"
      />
    </template>
  </div>
</template>

<script>
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import form from '@baserow/modules/core/mixins/form'
import applicationContext from '@baserow/modules/builder/mixins/applicationContext'
import { required, maxLength } from 'vuelidate/lib/validators'
import { DATA_PROVIDERS_ALLOWED_DATA_SOURCES } from '@baserow/modules/builder/enums'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'

export default {
  name: 'DataSourceForm',
  components: { IntegrationDropdown },
  mixins: [form, applicationContext],
  provide() {
    return { dataProvidersAllowed: DATA_PROVIDERS_ALLOWED_DATA_SOURCES }
  },
  props: {
    builder: {
      type: Object,
      required: true,
    },
    dataSource: {
      type: Object,
      required: false,
      default: () => ({}),
    },
    page: {
      type: Object,
      required: true,
    },
    integrations: {
      type: Array,
      required: true,
    },
    create: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      allowedValues: ['name', 'integration_id', 'type'],
      values: { name: '', integration_id: null, type: null },
    }
  },
  computed: {
    computedType: {
      get() {
        return this.values.type
      },
      set(newValue) {
        this.values.type = newValue
        this.values.name = this.suggestedName
        if (this.availableIntegrations.length === 1) {
          this.values.integration_id = this.availableIntegrations[0].id
        }
      },
    },
    integration() {
      return this.integrations.find(
        (integration) => integration.id === this.values.integration_id
      )
    },
    serviceTypes() {
      return this.$registry.getOrderedList('service')
    },
    serviceType() {
      return this.values.type
        ? this.$registry.get('service', this.values.type)
        : null
    },
    existingNames() {
      return this.$store.getters['dataSource/getPageDataSources'](this.page)
        .filter(({ id }) => this.create || id !== this.defaultValues.id)
        .map(({ name }) => name)
    },
    suggestedName() {
      if (!this.serviceType) {
        return getNextAvailableNameInSequence(
          this.$t('dataSourceForm.defaultName'),
          this.existingNames
        )
      }

      return getNextAvailableNameInSequence(
        this.serviceType.name,
        this.existingNames
      )
    },
    availableIntegrations() {
      return this.serviceType
        ? this.integrations.filter(
            ({ type }) => type === this.serviceType.integrationType.getType()
          )
        : []
    },
    serviceTypesPerIntegration() {
      return this.$registry
        .getOrderedList('integration')
        .map((integrationType) => [
          integrationType,
          this.serviceTypes.filter(
            (serviceType) => serviceType.integrationType === integrationType
          ),
        ])
    },
    nameError() {
      if (!this.$v.values.name.$dirty) {
        return ''
      }
      return !this.$v.values.name.required
        ? this.$t('error.requiredField')
        : !this.$v.values.name.maxLength
        ? this.$t('error.maxLength', { max: 255 })
        : !this.$v.values.name.unique
        ? this.$t('dataSourceForm.errorUniqueName')
        : ''
    },
    typeError() {
      if (!this.$v.values.type.$dirty) {
        return ''
      }
      return !this.$v.values.type.required ? this.$t('error.requiredField') : ''
    },
    integrationError() {
      if (!this.$v.values.integration_id.$dirty) {
        return ''
      }
      return !this.$v.values.integration_id.required
        ? this.$t('error.requiredField')
        : ''
    },
  },
  methods: {
    mustHaveUniqueName(param) {
      return !this.existingNames.includes(param.trim())
    },
  },
  validations() {
    return {
      values: {
        name: {
          required,
          maxLength: maxLength(255),
          unique: this.mustHaveUniqueName,
        },
        integration_id: {
          required,
        },
        type: {
          required,
        },
      },
    }
  },
}
</script>
