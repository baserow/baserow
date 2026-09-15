<template>
  <div class="context__form-container">
    <FormGroup
      small-label
      :label="$t('selectAIModelForm.AIType')"
      :error="fieldHasErrors('ai_generative_ai_type')"
      required
    >
      <Dropdown
        v-model="v$.values.ai_generative_ai_type.$model"
        class="dropdown--floating"
        :disabled="modelsLoading"
        :error="fieldHasErrors('ai_generative_ai_type')"
        :fixed-items="true"
        :show-search="false"
        @hide="v$.values.ai_generative_ai_type.$touch"
        @change="$refs.aiModel.select(baseAvailableModels[0])"
      >
        <DropdownItem
          v-for="provider in availableProviders"
          :key="provider.type"
          :name="provider.name"
          :value="provider.type"
        />
      </Dropdown>
      <template #error>
        <div v-if="v$.values.ai_generative_ai_type.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('selectAIModelForm.AIModel')"
      :error="modelFieldInvalid"
      required
    >
      <Dropdown
        ref="aiModel"
        v-model="v$.values.ai_generative_ai_model.$model"
        class="dropdown--floating"
        :disabled="modelsLoading"
        :error="modelFieldInvalid"
        :fixed-items="true"
        :show-search="false"
        @hide="v$.values.ai_generative_ai_model.$touch"
      >
        <DropdownItem
          v-for="model in availableModels"
          :key="model"
          :name="model"
          :value="model"
          :disabled="
            selectedModelUnavailable && model === values.ai_generative_ai_model
          "
        />
      </Dropdown>
      <template #error>
        <div v-if="v$.values.ai_generative_ai_model.required.$invalid">
          {{ $t('error.requiredField') }}
        </div>
        <div
          v-else-if="
            selectedModelUnavailable ||
            v$.values.ai_generative_ai_model.available.$invalid
          "
        >
          {{ $t('selectAIModelForm.modelUnavailable') }}
        </div>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('selectAIModelForm.temperatureLabel')"
      :help-icon-tooltip="
        $t('selectAIModelForm.temperatureDescription', { max: maxTemperature })
      "
      :error="fieldHasErrors('ai_temperature')"
      required
    >
      <FormInput
        v-model="v$.values.ai_temperature.$model"
        :step="0.1"
        :min="0"
        :max="maxTemperature"
        type="number"
        :error="fieldHasErrors('ai_temperature')"
      ></FormInput>
      <template #error>
        <span v-if="v$.values.ai_temperature.decimal.$invalid">
          {{ $t('error.decimalField') }}
        </span>
        <span v-else-if="v$.values.ai_temperature.minValue.$invalid">
          {{ $t('error.minValueField', { min: 0 }) }}
        </span>
        <span v-else-if="v$.values.ai_temperature.maxValue.$invalid">
          {{ $t('error.maxValueField', { max: maxTemperature }) }}
        </span>
      </template>
    </FormGroup>
  </div>
</template>

<script>
import { useVuelidate } from '@vuelidate/core'
import { mapGetters } from 'vuex'
import { required, decimal, minValue, maxValue } from '@vuelidate/validators'
import modal from '@baserow/modules/core/mixins/modal'
import form from '@baserow/modules/core/mixins/form'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'
import { FF_AI_PROVIDERS } from '@baserow/modules/core/plugins/featureFlags'

export default {
  name: 'SelectAIModelForm',
  mixins: [form, modal],
  props: {
    database: {
      type: Object,
      required: true,
    },
    featureType: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['ai-type-changed'],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'ai_generative_ai_type',
        'ai_generative_ai_model',
        'ai_temperature',
      ],
      values: {
        ai_generative_ai_type: null,
        ai_generative_ai_model: null,
        ai_temperature: 0.1,
      },
      temperature: null,
      modelsLoading: true,
    }
  },
  computed: {
    ...mapGetters({
      settings: 'settings/get',
    }),
    // Return the reactive object that can be updated in runtime.
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    /**
     * @returns {boolean} Whether database provider eligibility is enforced.
     */
    aiProvidersEnabled() {
      return this.$featureFlagIsEnabled(FF_AI_PROVIDERS)
    },
    enabledModelsByType() {
      return this.featureType
        ? getEnabledModelsForAIProviderFeature(
            this.workspace,
            this.featureType,
            this.aiProvidersEnabled
          )
        : this.workspace.generative_ai_models_enabled || {}
    },
    /**
     * @returns {Array<{type: string, name: string}>} Installed providers with
     *   enabled models, excluding any unavailable saved selection.
     */
    baseAvailableProviders() {
      const allProviders = this.$registry.getAll('generativeAIModel')
      return Object.keys(this.enabledModelsByType)
        .filter((type) => allProviders[type])
        .map((type) => ({ type, name: allProviders[type].getName() }))
    },
    /**
     * @returns {Array<{type: string, name: string}>} Provider options, retaining
     *   an unavailable saved provider for diagnosis when eligibility is enforced.
     */
    availableProviders() {
      const providers = this.baseAvailableProviders
      const current = this.values.ai_generative_ai_type
      if (
        this.aiProvidersEnabled &&
        current &&
        !providers.some((provider) => provider.type === current)
      ) {
        const modelType = this.$registry.getAll('generativeAIModel')[current]
        return [
          ...providers,
          { type: current, name: modelType ? modelType.getName() : current },
        ]
      }
      return providers
    },
    /**
     * @returns {string[]} Models enabled for the selected provider, excluding an
     *   unavailable saved model.
     */
    baseAvailableModels() {
      return this.getAIModelsPerType(this.values.ai_generative_ai_type)
    },
    /**
     * @returns {string[]} Model options, retaining an unavailable saved model for
     *   diagnosis when eligibility is enforced.
     */
    availableModels() {
      const models = this.baseAvailableModels
      const current = this.values.ai_generative_ai_model
      if (this.aiProvidersEnabled && current && !models.includes(current)) {
        return [...models, current]
      }
      return models
    },
    /**
     * @returns {boolean} Whether eligibility prevents using the saved model.
     */
    selectedModelUnavailable() {
      const current = this.values.ai_generative_ai_model
      return Boolean(
        this.aiProvidersEnabled &&
        current &&
        !this.baseAvailableModels.includes(current)
      )
    },
    /**
     * @returns {boolean} Whether the model field renders in its error state.
     */
    modelFieldInvalid() {
      return (
        this.fieldHasErrors('ai_generative_ai_model') ||
        this.selectedModelUnavailable
      )
    },
    maxTemperature() {
      const modelType =
        this.$registry.getAll('generativeAIModel')[
          this.values.ai_generative_ai_type
        ]
      return modelType ? modelType.getMaxTemperature() : 2
    },
  },
  watch: {
    'values.ai_generative_ai_type': function (newValue, oldValue) {
      this.$emit('ai-type-changed', newValue)
    },
    'values.ai_temperature'(newValue, oldValue) {
      if (newValue !== oldValue) {
        this.temperature = newValue || ''
      }
    },
    temperature(newValue, oldValue) {
      if (newValue !== oldValue) {
        if (!newValue) {
          this.values.ai_temperature = null
        } else {
          const value = parseFloat(newValue)
          if (!isNaN(value)) {
            this.values.ai_temperature = parseFloat(newValue) || null
          }
        }
      }
    },
  },
  async mounted() {
    try {
      await this.$store.dispatch(
        'workspace/refreshGenerativeAIModels',
        this.database.workspace.id
      )
    } catch (error) {
      notifyIf(error)
    } finally {
      this.modelsLoading = false
    }

    if (
      !this.values.ai_generative_ai_type &&
      this.baseAvailableProviders.length > 0
    ) {
      const aiType = this.baseAvailableProviders[0].type
      this.values.ai_generative_ai_type = aiType
      const aiModels = this.getAIModelsPerType(aiType)
      this.values.ai_generative_ai_model = aiModels[0] || null
    }
  },
  methods: {
    getAIModelsPerType(aiType) {
      return this.enabledModelsByType[aiType] || []
    },
  },
  validations() {
    return {
      values: {
        ai_generative_ai_type: { required },
        ai_generative_ai_model: {
          required,
          available: (value) =>
            !value || this.baseAvailableModels.includes(value),
        },
        ai_temperature: {
          decimal,
          minValue: minValue(0),
          maxValue: maxValue(this.maxTemperature),
        },
      },
    }
  },
}
</script>
