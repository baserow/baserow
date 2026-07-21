<template>
  <Modal ref="modal" small @hidden="$emit('hidden')">
    <h2 class="box__title">
      {{
        model ? $t('aiProviderAdmin.editModel') : $t('aiProviderAdmin.addModel')
      }}
    </h2>
    <FormGroup
      :label="$t('aiProviderAdmin.modelIdentifier')"
      :error-message="modelIdentifierError"
      required
      class="margin-bottom-2"
    >
      <AIProviderModelCombobox
        v-if="!model"
        v-model="values.model_identifier"
        :suggestions="availableSuggestions"
        :loading="discoveryLoading"
        :unavailable="discoveryUnavailable"
        :error="Boolean(modelIdentifierError)"
        :placeholder="$t('aiProviderAdmin.modelIdentifier')"
        @focus="discoverModelsIfNeeded"
        @input="modelIdentifierError = ''"
      />
      <FormInput
        v-else
        v-model="values.model_identifier"
        :error="Boolean(modelIdentifierError)"
        @input="modelIdentifierError = ''"
      />
      <div v-if="!model" class="ai-provider-form__hint">
        {{ $t('aiProviderAdmin.modelDiscoveryHelp') }}
      </div>
      <template v-if="modelIdentifierDescription" #helper>
        <MarkdownIt :content="modelIdentifierDescription" />
      </template>
    </FormGroup>
    <div class="actions">
      <ul class="action__links">
        <li>
          <a @click="hide()">{{ $t('action.cancel') }}</a>
        </li>
      </ul>
      <Button :loading="loading" :disabled="!isValid" @click="submit">
        {{ $t('action.save') }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import AIProviderModelCombobox from '@baserow/modules/core/components/ai/AIProviderModelCombobox'
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'AIProviderModelFormModal',
  components: { AIProviderModelCombobox },
  mixins: [modal],
  props: {
    provider: { type: Object, required: true },
    model: { type: Object, default: null },
  },
  emits: ['hidden', 'saved'],
  data() {
    return {
      loading: false,
      modelIdentifierError: '',
      discoveryLoading: false,
      discoveryFailed: false,
      discoverySupported: true,
      discoveryAttempted: false,
      discoveredModels: [],
      values: {
        model_identifier: this.model?.model_identifier || '',
      },
    }
  },
  computed: {
    availableSuggestions() {
      const configuredModels = new Set(
        (this.provider.models || []).map((model) => model.model_identifier)
      )
      return this.discoveredModels.filter(
        (modelIdentifier) => !configuredModels.has(modelIdentifier)
      )
    },
    discoveryUnavailable() {
      return this.discoveryFailed || !this.discoverySupported
    },
    modelIdentifierDescription() {
      const providerType = this.provider.provider_type
      if (!this.$registry.exists('generativeAIModel', providerType)) {
        return ''
      }
      return (
        this.$registry
          .get('generativeAIModel', providerType)
          .getModelIdentifierDescription() || ''
      )
    },
    isValid() {
      return Boolean(this.values.model_identifier.trim())
    },
  },
  methods: {
    discoverModelsIfNeeded() {
      if (!this.discoveryAttempted || this.discoveryFailed) {
        this.discoverModels()
      }
    },
    async discoverModels() {
      if (this.discoveryLoading) {
        return
      }
      this.discoveryAttempted = true
      this.discoveryLoading = true
      this.discoveryFailed = false
      try {
        const result = await this.$store.dispatch(
          'aiProvider/discoverModels',
          this.provider.provider_type
        )
        this.discoveredModels = result.models || []
        this.discoverySupported = result.supported !== false
      } catch {
        this.discoveredModels = []
        this.discoveryFailed = true
      } finally {
        this.discoveryLoading = false
      }
    },
    async submit() {
      this.modelIdentifierError = ''
      this.loading = true
      const values = {
        model_identifier: this.values.model_identifier.trim(),
      }
      try {
        const result = this.model
          ? await this.$store.dispatch('aiProvider/updateModel', {
              modelId: this.model.id,
              values,
            })
          : await this.$store.dispatch('aiProvider/createModel', {
              providerId: this.provider.id,
              values,
            })
        this.$emit('saved', result)
        this.hide()
      } catch (error) {
        const errorCode = error.response?.data?.error
        const detail = error.response?.data?.detail
        const errorMessage = detail?.message || detail
        if (errorCode === 'ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED') {
          this.modelIdentifierError = errorMessage
          return
        }
        this.$store.dispatch('toast/error', {
          title: this.$t('aiProviderAdmin.saveModelError'),
          message: errorMessage,
        })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
