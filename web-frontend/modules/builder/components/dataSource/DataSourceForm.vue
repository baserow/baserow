<template>
  <div class="data-source-form">
    <div class="data-source-form__header">
      <div class="data-source-form__header-form">
        <FormGroup
          :label="$t('dataSourceForm.actionLabel')"
          small-label
          required
          :error-message="getFirstErrorMessage('type')"
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
          :error-message="getFirstErrorMessage('integration_id')"
        >
          <IntegrationDropdown
            v-model="v$.values.integration_id.$model"
            class="data-source-form__integration-dropdown"
            :application="builder"
            :integrations="integrations"
            :disabled="!v$.values.type.$model"
            :integration-type="serviceType?.integrationType"
          />
        </FormGroup>
        <FormGroup
          :label="$t('dataSourceForm.nameLabel')"
          small-label
          required
          :error-message="getFirstErrorMessage('name')"
        >
          <FormInput
            v-model="v$.values.name.$model"
            class="data-source-form__name-input"
            :placeholder="$t('dataSourceForm.namePlaceholder')"
            @blur="v$.values.name.$touch()"
          />
        </FormGroup>
      </div>
    </div>
    <template v-if="!create && integration">
      <component
        :is="serviceType.formComponent"
        ref="subForm"
        :application="builder"
        :service="dataSource"
        :service-type="serviceType"
        :default-values="defaultValues"
        :context-data="integration.context_data"
        @values-changed="emitChange($event)"
      />
    </template>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import form from '@baserow/modules/core/mixins/form'
import applicationContext from '@baserow/modules/builder/mixins/applicationContext'
import { required, maxLength, helpers } from '@vuelidate/validators'
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
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
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
        this.v$.values.type.$model = newValue
        this.v$.values.name.$model = this.suggestedName
        if (this.availableIntegrations.length === 1) {
          this.v$.values.integration_id.$model =
            this.availableIntegrations[0].id
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
    dataSourceServiceTypes() {
      return this.serviceTypes.filter(({ isDataSource }) => isDataSource)
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
          this.dataSourceServiceTypes.filter(
            (serviceType) => serviceType.integrationType === integrationType
          ),
        ])
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
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('error.maxLength', { max: 255 }),
            maxLength(255)
          ),
          unique: helpers.withMessage(
            this.$t('dataSourceForm.errorUniqueName'),
            this.mustHaveUniqueName
          ),
        },
        integration_id: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
        type: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
        },
      },
    }
  },
}
</script>
