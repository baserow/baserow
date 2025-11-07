<template>
  <form @submit.prevent>
    <FormGroup
      small-label
      :label="$t('aiAgentServiceForm.integrationLabel')"
      required
      class="margin-bottom-2"
    >
      <IntegrationDropdown
        v-model="values.integration_id"
        :application="application"
        :integrations="integrations"
        :integration-type="integrationType"
      />
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('aiAgentServiceForm.providerLabel')"
      required
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="values.ai_generative_ai_type"
        :placeholder="$t('aiAgentServiceForm.providerPlaceholder')"
      >
        <DropdownItem
          v-for="provider in availableProviders"
          :key="provider.type"
          :name="provider.name"
          :value="provider.type"
        >
        </DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      v-if="values.ai_generative_ai_type"
      small-label
      :label="$t('aiAgentServiceForm.modelLabel')"
      required
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="values.ai_generative_ai_model"
        :placeholder="$t('aiAgentServiceForm.modelPlaceholder')"
      >
        <DropdownItem
          v-for="model in availableModels"
          :key="model"
          :name="model"
          :value="model"
        >
        </DropdownItem>
      </Dropdown>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('aiAgentServiceForm.promptLabel')"
      :error="v$.values.ai_prompt.$error"
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.ai_prompt"
        :placeholder="$t('aiAgentServiceForm.promptPlaceholder')"
      />
      <template #error>
        <span v-if="!v$.values.ai_prompt.required" class="error">
          {{ $t('error.requiredField') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('aiAgentServiceForm.outputTypeLabel')"
      required
      class="margin-bottom-2"
    >
      <RadioGroup
        v-model="values.ai_output_type"
        :options="outputTypeOptions"
      />
      <template #helper>
        {{ $t('aiAgentServiceForm.outputTypeHelp') }}
      </template>
    </FormGroup>

    <FormGroup
      v-if="values.ai_output_type === 'choice'"
      small-label
      :label="$t('aiAgentServiceForm.choicesLabel')"
      :error="v$.values.ai_choices.$error"
      required
      class="margin-bottom-2"
    >
      <div
        v-for="(choice, index) in values.ai_choices"
        :key="index"
        class="margin-bottom-1 flex"
      >
        <FormInput
          :value="choice"
          :placeholder="$t('aiAgentServiceForm.choicePlaceholder')"
          class="flex-1 margin-right-1"
          @input="updateChoice(index, $event)"
        />
        <Button
          type="secondary"
          icon="iconoir-bin"
          @click="removeChoice(index)"
        />
      </div>
      <Button type="secondary" size="small" @click="addChoice">
        <i class="iconoir-plus"></i>
        {{ $t('aiAgentServiceForm.addChoice') }}
      </Button>
      <template #error>
        <span v-if="!v$.values.ai_choices.hasValidChoice" class="error">
          {{ $t('aiAgentServiceForm.choicesRequired') }}
        </span>
      </template>
    </FormGroup>

    <FormGroup
      small-label
      :label="$t('aiAgentServiceForm.temperatureLabel')"
      class="margin-bottom-2"
    >
      <FormInput
        v-model.number="values.ai_temperature"
        type="number"
        :min="0"
        :max="maxTemperature"
        :step="0.1"
        :placeholder="$t('aiAgentServiceForm.temperaturePlaceholder')"
      />
      <template #helper>
        {{ $t('aiAgentServiceForm.temperatureHelp') }}
      </template>
    </FormGroup>
  </form>
</template>

<script>
import { required } from '@vuelidate/validators'
import { useVuelidate } from '@vuelidate/core'
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import IntegrationDropdown from '@baserow/modules/core/components/integrations/IntegrationDropdown'
import { AIIntegrationType } from '@baserow/modules/integrations/ai/integrationTypes'

export default {
  name: 'AIAgentServiceForm',
  components: {
    InjectedFormulaInput,
    IntegrationDropdown,
  },
  mixins: [form],
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate() }
  },
  data() {
    return {
      allowedValues: [
        'integration_id',
        'ai_generative_ai_type',
        'ai_generative_ai_model',
        'ai_output_type',
        'ai_temperature',
        'ai_prompt',
        'ai_choices',
      ],
      values: {
        integration_id: null,
        ai_generative_ai_type: null,
        ai_generative_ai_model: null,
        ai_output_type: 'text',
        ai_temperature: null,
        ai_prompt: '',
        ai_choices: [],
      },
    }
  },
  computed: {
    integrations() {
      if (!this.application) {
        return []
      }
      const allIntegrations = this.$store.getters[
        'integration/getIntegrations'
      ](this.application)
      return allIntegrations.filter(
        (integration) => integration.type === AIIntegrationType.getType()
      )
    },
    integrationType() {
      return this.$registry.get('integration', AIIntegrationType.getType())
    },
    integration() {
      return this.$store.getters['integration/getIntegrationById'](
        this.application,
        this.values.integration_id
      )
    },
    workspace() {
      return this.$store.getters['workspace/get'](this.application.workspace.id)
    },
    availableProviders() {
      if (!this.integration) {
        return []
      }

      const workspaceEnabled =
        this.workspace?.generative_ai_models_enabled || {}
      const integrationSettings = this.integration.ai_settings || {}
      const allProviders = this.$registry.getAll('generativeAIModel')
      return Object.keys(allProviders)
        .filter((type) => {
          // Provider is available if it's configured at any level:
          // 1. Has env vars (checked by backend when getting enabled models)
          // 2. Set on workspace level
          // 3. Set on integration level

          // Check if provider has models in integration settings
          if (integrationSettings[type]) {
            const models = integrationSettings[type].models || []
            if (models.length > 0) {
              return true
            }
          }

          // Check if provider has models in workspace settings
          if (workspaceEnabled[type] && workspaceEnabled[type].length > 0) {
            return true
          }

          return false
        })
        .map((type) => {
          const modelType = this.$registry.get('generativeAIModel', type)
          return {
            type,
            name: modelType ? modelType.getName() : type,
          }
        })
    },
    availableModels() {
      if (!this.integration || !this.values.ai_generative_ai_type) {
        return []
      }

      const integrationSettings = this.integration.ai_settings || {}
      const workspaceEnabled =
        this.workspace?.generative_ai_models_enabled || {}

      // If provider is overridden in integration, use integration models.
      if (integrationSettings[this.values.ai_generative_ai_type]) {
        return (
          integrationSettings[this.values.ai_generative_ai_type].models || []
        )
      }

      // Otherwise use workspace models
      return workspaceEnabled[this.values.ai_generative_ai_type] || []
    },
    maxTemperature() {
      if (!this.values.ai_generative_ai_type) {
        return 2
      }
      const modelType = this.$registry.get(
        'generativeAIModel',
        this.values.ai_generative_ai_type
      )
      return modelType ? modelType.getMaxTemperature() : 2
    },
    outputTypeOptions() {
      return [
        {
          label: this.$t('aiAgentServiceForm.outputTypeText'),
          value: 'text',
        },
        {
          label: this.$t('aiAgentServiceForm.outputTypeChoice'),
          value: 'choice',
        },
      ]
    },
  },
  watch: {
    /**
     * When integration changes, validate provider and model are still available, Only
     * trigger if oldValue exists (not on initial mount)
     */
    'values.integration_id'(newValue, oldValue) {
      if (oldValue && newValue !== oldValue) {
        // Check if current provider is still available
        const availableProviderTypes = this.availableProviders.map(
          (p) => p.type
        )
        if (
          this.values.ai_generative_ai_type &&
          !availableProviderTypes.includes(this.values.ai_generative_ai_type)
        ) {
          // Provider no longer available, clear it and model
          this.values.ai_generative_ai_type = null
          this.values.ai_generative_ai_model = null
        } else if (this.values.ai_generative_ai_type) {
          // Provider still available, check if model is still available
          const models = this.availableModels
          if (
            this.values.ai_generative_ai_model &&
            !models.includes(this.values.ai_generative_ai_model)
          ) {
            // Model no longer available, auto-select first available
            this.values.ai_generative_ai_model =
              models.length > 0 ? models[0] : null
          }
        }
      }
    },
    /**
     * Auto-select first available model when provider changes. Only trigger if oldValue
     * exists (not on initial mount).
     */
    'values.ai_generative_ai_type'(newValue, oldValue) {
      if (oldValue && newValue !== oldValue) {
        const models = this.availableModels
        this.values.ai_generative_ai_model =
          models.length > 0 ? models[0] : null
      }
    },
    /**
     * Clear choices when switching away from choice output type. Only trigger if
     * oldValue exists (not on initial mount)
     */
    'values.ai_output_type'(newValue, oldValue) {
      if (oldValue && newValue !== 'choice') {
        this.values.ai_choices = []
      }
    },
  },
  methods: {
    addChoice() {
      this.values.ai_choices.push('')
    },
    updateChoice(index, value) {
      this.$set(this.values.ai_choices, index, value)
    },
    removeChoice(index) {
      this.values.ai_choices.splice(index, 1)
    },
  },
  validations() {
    const hasValidChoice = (value) => {
      if (this.values.ai_output_type !== 'choice') {
        return true
      }
      // Must have at least one non-empty choice
      return (
        value &&
        Array.isArray(value) &&
        value.length > 0 &&
        value.some((c) => c && c.trim())
      )
    }

    return {
      values: {
        ai_prompt: { required },
        ai_choices: {
          hasValidChoice,
        },
      },
    }
  },
}
</script>
