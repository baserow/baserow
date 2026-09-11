<template>
  <Modal
    ref="modal"
    small
    :can-close="!saveConfirmation"
    @hidden="$emit('hidden')"
  >
    <h2 class="box__title">
      {{
        model ? $t('aiProviderAdmin.editModel') : $t('aiProviderAdmin.addModel')
      }}
    </h2>
    <FormGroup
      :label="$t('aiProviderAdmin.modelIdentifier')"
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
      <p
        v-if="modelIdentifierError"
        class="control__messages--error ai-provider-form__field-error"
      >
        {{ modelIdentifierError }}
      </p>
      <div v-if="!model" class="ai-provider-form__hint">
        {{ $t('aiProviderAdmin.modelDiscoveryHelp') }}
      </div>
      <template v-if="modelIdentifierDescription" #helper>
        <MarkdownIt :content="modelIdentifierDescription" />
      </template>
    </FormGroup>
    <AIProviderModelFeatureSelector
      v-model="values.feature_types"
      class="margin-bottom-2"
    />
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
  <AIProviderConfirmModal
    v-if="saveConfirmation"
    ref="confirmModal"
    :title="saveConfirmation.title"
    :message="
      modelUsageMessage(saveConfirmation.usage, saveConfirmation.description)
    "
    :confirm-label="$t('action.save')"
    :loading="loading"
    @hidden="saveConfirmation = null"
    @confirm="confirmSave"
  />
</template>

<script>
import AIProviderConfirmModal from '@baserow/modules/core/components/ai/AIProviderConfirmModal'
import AIProviderModelCombobox from '@baserow/modules/core/components/ai/AIProviderModelCombobox'
import AIProviderModelFeatureSelector from '@baserow/modules/core/components/ai/AIProviderModelFeatureSelector'
import aiProviderModelUsage from '@baserow/modules/core/mixins/aiProviderModelUsage'
import modal from '@baserow/modules/core/mixins/modal'
import { aiProviderErrorMessage } from '@baserow/modules/core/utils/aiProvider'

export default {
  name: 'AIProviderModelFormModal',
  components: {
    AIProviderConfirmModal,
    AIProviderModelCombobox,
    AIProviderModelFeatureSelector,
  },
  mixins: [modal, aiProviderModelUsage],
  props: {
    provider: { type: Object, required: true },
    model: { type: Object, default: null },
    workspaceId: { type: Number, default: null },
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
      saveConfirmation: null,
      values: {
        model_identifier: this.model?.model_identifier || '',
        feature_types:
          this.model?.feature_types ||
          this.$registry
            .getOrderedList('aiProviderModelFeature')
            .map((feature) => feature.getType()),
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
          this.workspaceId === null
            ? this.provider.provider_type
            : {
                providerType: this.provider.provider_type,
                workspaceId: this.workspaceId,
              }
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
    /**
     * A rename orphans every consumer, because they persist the identifier
     * string rather than the model row id.
     *
     * @returns {Promise<{title: string, description: string, usage: Object}|null>}
     *   The confirmation this save needs, or null when nothing depends on it.
     */
    async requiredSaveConfirmation() {
      if (!this.model) {
        return null
      }
      const renamed =
        this.values.model_identifier.trim() !== this.model.model_identifier
      const removed = (this.model.feature_types || []).filter(
        (featureType) => !this.values.feature_types.includes(featureType)
      )
      if (!renamed && removed.length === 0) {
        return null
      }
      const { usage, blockingFeatureTypes } = await this.lookupModelUsage(
        this.model.id,
        this.workspaceId
      )
      const atRisk = {
        usage: usage.filter(
          (entry) =>
            entry.count > 0 && (renamed || removed.includes(entry.featureType))
        ),
        blockingFeatureTypes: renamed ? blockingFeatureTypes : [],
      }
      if (!this.modelHasDependents(atRisk)) {
        return null
      }
      const prefix = renamed
        ? 'aiProviderAdmin.modelIdentifierRenamed'
        : 'aiProviderAdmin.modelFeaturesRemoved'
      return {
        title: this.$t(`${prefix}Title`, { name: this.model.model_identifier }),
        description: this.$t(`${prefix}Description`),
        usage: atRisk,
      }
    },
    async submit() {
      this.modelIdentifierError = ''
      this.loading = true
      try {
        const confirmation = await this.requiredSaveConfirmation()
        if (confirmation) {
          this.saveConfirmation = confirmation
          this.$nextTick(() => this.$refs.confirmModal.show())
          return
        }
        await this.save()
      } finally {
        this.loading = false
      }
    },
    async confirmSave() {
      this.loading = true
      try {
        await this.save()
      } finally {
        this.loading = false
        this.$refs.confirmModal?.hide()
      }
    },
    async save() {
      const values = {
        model_identifier: this.values.model_identifier.trim(),
        feature_types: this.values.feature_types,
      }
      try {
        const result = this.model
          ? await this.$store.dispatch('aiProvider/updateModel', {
              modelId: this.model.id,
              values,
              ...(this.workspaceId === null
                ? {}
                : { workspaceId: this.workspaceId }),
            })
          : await this.$store.dispatch('aiProvider/createModel', {
              providerId: this.provider.id,
              values,
              ...(this.workspaceId === null
                ? {}
                : { workspaceId: this.workspaceId }),
            })
        this.$emit('saved', result)
        this.hide()
      } catch (error) {
        const errorMessage = aiProviderErrorMessage(error)
        if (
          error.response?.data?.error ===
          'ERROR_AI_PROVIDER_MODEL_ALREADY_CONFIGURED'
        ) {
          this.modelIdentifierError = errorMessage
          return
        }
        this.$store.dispatch('toast/error', {
          title: this.$t('aiProviderAdmin.saveModelError'),
          message: errorMessage,
        })
      }
    },
  },
}
</script>
