<template>
  <Modal ref="modal" @hidden="$emit('hidden')">
    <h2 class="box__title">
      {{
        provider
          ? $t('aiProviderAdmin.editProvider')
          : $t('aiProviderAdmin.addProvider')
      }}
    </h2>

    <FormGroup
      :label="$t('aiProviderAdmin.providerType')"
      :error-message="providerTypeError"
      required
      class="margin-bottom-2"
    >
      <Dropdown
        v-model="values.provider_type"
        :disabled="!!provider"
        :error="Boolean(providerTypeError)"
      >
        <DropdownItem
          v-for="providerType in providerTypes"
          :key="providerType.type"
          :name="providerType.name"
          :value="providerType.type"
        />
      </Dropdown>
    </FormGroup>

    <FormGroup
      v-if="selectedType && selectedType.uses_api_key"
      :label="$t('aiProviderAdmin.apiKey')"
      required
      class="margin-bottom-2"
    >
      <template v-if="provider && !apiKeyEditing">
        <div class="ai-provider-form__secret-status">
          <Button type="secondary" size="small" @click="apiKeyEditing = true">
            {{ $t('aiProviderAdmin.changeApiKey') }}
          </Button>
        </div>
      </template>
      <template v-else>
        <FormInput
          v-model="values.api_key"
          type="password"
          autocomplete="off"
        />
        <div v-if="provider" class="ai-provider-form__hint">
          {{ $t('aiProviderAdmin.apiKeyUpdateHint') }}
        </div>
      </template>
      <template v-if="settingDescription('api_key')" #helper>
        <MarkdownIt :content="settingDescription('api_key')" />
      </template>
    </FormGroup>
    <FormGroup
      v-for="field in selectedType?.extra_fields || []"
      :key="field.name"
      :label="extraFieldLabel(field.name)"
      :required="field.required && !field.allow_blank"
      class="margin-bottom-2"
    >
      <FormInput v-model="extraSettings[field.name]" />
      <template v-if="settingDescription(field.name)" #helper>
        <MarkdownIt :content="settingDescription(field.name)" />
      </template>
    </FormGroup>

    <FormGroup
      v-if="!provider"
      :label="$t('aiProviderAdmin.models')"
      class="margin-bottom-2"
    >
      <div
        v-for="(model, index) in models"
        :key="index"
        class="ai-provider-form__model-entry"
      >
        <div class="ai-provider-form__model-row">
          <AIProviderModelCombobox
            v-model="model.model_identifier"
            :suggestions="availableSuggestionsFor(model)"
            :loading="discoveryLoading"
            :unavailable="discoveryUnavailable"
            :placeholder="$t('aiProviderAdmin.modelIdentifier')"
            @focus="discoverModelsIfNeeded"
          />
          <Button
            type="secondary"
            icon="iconoir-cancel"
            :title="$t('aiProviderAdmin.removeModel')"
            :aria-label="$t('aiProviderAdmin.removeModel')"
            @click="models.splice(index, 1)"
          />
        </div>
        <AIProviderModelFeatureSelector v-model="model.feature_types" />
      </div>
      <Button type="secondary" size="small" @click="addModel">
        <i class="iconoir-plus" /> {{ $t('aiProviderAdmin.addModel') }}
      </Button>
      <div class="ai-provider-form__hint">
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
import AIProviderModelFeatureSelector from '@baserow/modules/core/components/ai/AIProviderModelFeatureSelector'
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'AIProviderFormModal',
  components: { AIProviderModelCombobox, AIProviderModelFeatureSelector },
  mixins: [modal],
  props: {
    provider: { type: Object, default: null },
    providerTypes: { type: Array, required: true },
    workspaceId: { type: Number, default: null },
  },
  emits: ['hidden', 'saved'],
  data() {
    const providerType =
      this.provider?.provider_type || this.providerTypes[0]?.type
    const defaultFeatureTypes = this.$registry
      .getOrderedList('aiProviderModelFeature')
      .map((feature) => feature.getType())
    return {
      loading: false,
      providerTypeError: '',
      apiKeyEditing: false,
      discoveryLoading: false,
      discoveryFailed: false,
      discoverySupported: true,
      discoveryAttempted: false,
      discoveredModels: [],
      values: {
        provider_type: providerType,
        api_key: '',
      },
      extraSettings: { ...(this.provider?.extra_settings || {}) },
      models: this.provider
        ? []
        : [{ model_identifier: '', feature_types: defaultFeatureTypes }],
    }
  },
  computed: {
    selectedType() {
      return this.providerTypes.find(
        (providerType) => providerType.type === this.values.provider_type
      )
    },
    selectedModelType() {
      const providerType = this.values.provider_type
      if (
        !providerType ||
        !this.$registry.exists('generativeAIModel', providerType)
      ) {
        return null
      }
      return this.$registry.get('generativeAIModel', providerType)
    },
    modelIdentifierDescription() {
      return this.selectedModelType?.getModelIdentifierDescription() || ''
    },
    discoveryUnavailable() {
      return this.discoveryFailed || !this.discoverySupported
    },
    isValid() {
      if (!this.values.provider_type) {
        return false
      }
      const apiKeyRequired =
        this.selectedType?.uses_api_key &&
        (!this.provider || this.apiKeyEditing)
      const requiredExtraSettingsPresent = (
        this.selectedType?.extra_fields || []
      ).every(
        (field) =>
          !field.required ||
          field.allow_blank ||
          Boolean(String(this.extraSettings[field.name] || '').trim())
      )
      return (
        (!apiKeyRequired || Boolean(this.values.api_key.trim())) &&
        requiredExtraSettingsPresent
      )
    },
  },
  watch: {
    'values.provider_type'() {
      this.providerTypeError = ''
      this.extraSettings = {}
      this.resetModelDiscovery()
    },
  },
  methods: {
    defaultFeatureTypes() {
      return this.$registry
        .getOrderedList('aiProviderModelFeature')
        .map((feature) => feature.getType())
    },
    emptyModel() {
      return {
        model_identifier: '',
        feature_types: this.defaultFeatureTypes(),
      }
    },
    addModel() {
      this.models.push(this.emptyModel())
    },
    availableSuggestionsFor(model) {
      const selectedModels = new Set(
        this.models
          .filter((candidate) => candidate !== model)
          .map((candidate) => candidate.model_identifier.trim())
          .filter(Boolean)
      )
      return this.discoveredModels.filter(
        (modelIdentifier) => !selectedModels.has(modelIdentifier)
      )
    },
    resetModelDiscovery() {
      this.discoveredModels = []
      this.discoveryFailed = false
      this.discoverySupported = true
      this.discoveryAttempted = false
    },
    discoverModelsIfNeeded() {
      if (!this.discoveryAttempted || this.discoveryFailed) {
        this.discoverModels()
      }
    },
    async discoverModels() {
      if (!this.values.provider_type || this.discoveryLoading) {
        return
      }
      this.discoveryAttempted = true
      this.discoveryLoading = true
      this.discoveryFailed = false
      try {
        const result = await this.$store.dispatch(
          'aiProvider/discoverModels',
          this.workspaceId === null
            ? this.values.provider_type
            : {
                providerType: this.values.provider_type,
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
    extraFieldLabel(name) {
      return this.$t(`aiProviderAdmin.extraField_${name}`)
    },
    settingDescription(name) {
      return this.selectedModelType?.getSetting(name)?.description || ''
    },
    getExtraSettings() {
      return Object.fromEntries(
        (this.selectedType?.extra_fields || [])
          .filter((field) =>
            Object.prototype.hasOwnProperty.call(this.extraSettings, field.name)
          )
          .map((field) => [field.name, this.extraSettings[field.name]])
      )
    },
    async submit() {
      this.providerTypeError = ''
      this.loading = true
      const values = {
        extra_settings: this.getExtraSettings(),
      }
      if (this.provider) {
        if (this.apiKeyEditing) values.api_key = this.values.api_key
      } else {
        values.provider_type = this.values.provider_type
        if (this.selectedType?.uses_api_key)
          values.api_key = this.values.api_key
        values.models = this.models
          .filter((model) => model.model_identifier.trim())
          .map((model) => ({
            model_identifier: model.model_identifier.trim(),
            feature_types: model.feature_types,
          }))
      }
      try {
        const action = this.provider ? 'aiProvider/update' : 'aiProvider/create'
        const payload = this.provider
          ? {
              providerId: this.provider.id,
              values,
              ...(this.workspaceId === null
                ? {}
                : { workspaceId: this.workspaceId }),
            }
          : this.workspaceId === null
            ? values
            : { values, workspaceId: this.workspaceId }
        const result = await this.$store.dispatch(action, payload)
        this.$emit('saved', result)
        this.hide()
      } catch (error) {
        const errorCode = error.response?.data?.error
        const detail = error.response?.data?.detail
        const errorMessage = detail?.message || detail
        if (errorCode === 'ERROR_AI_PROVIDER_TYPE_ALREADY_CONFIGURED') {
          this.providerTypeError = errorMessage
          return
        }
        this.$store.dispatch('toast/error', {
          title: this.$t('aiProviderAdmin.saveError'),
          message: errorMessage,
        })
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
