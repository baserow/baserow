<template>
  <Modal ref="modal" @hidden="$emit('hidden')">
    <h2 class="box__title">
      {{ provider ? $t('aiProviderAdmin.editProvider') : $t('aiProviderAdmin.addProvider') }}
    </h2>
    <div>
      <FormGroup
        :label="$t('aiProviderAdmin.providerType')"
        required
        class="margin-bottom-2"
      >
        <Dropdown
          v-model="values.provider_type"
          :disabled="!!provider"
        >
          <DropdownItem
            v-for="pType in providerTypes"
            :key="pType"
            :name="pType"
            :value="pType"
          />
        </Dropdown>
      </FormGroup>

      <FormGroup
        :label="$t('aiProviderAdmin.name')"
        required
        class="margin-bottom-2"
      >
        <FormInput v-model="values.name" />
      </FormGroup>

      <FormGroup
        v-if="requiresApiKey"
        :label="$t('aiProviderAdmin.apiKey')"
        required
        class="margin-bottom-2"
      >
        <template v-if="provider && !editingApiKey">
          <div class="ai-provider-form__api-key-row">
            <FormInput
              :value="provider.has_api_key ? '••••••••••••••••' : ''"
              disabled
              class="ai-provider-form__api-key-input"
            />
            <a
              class="ai-provider-form__api-key-toggle"
              :title="$t('aiProviderAdmin.replaceApiKey')"
              @click="startEditApiKey"
            >
              <i class="iconoir-edit-pencil" />
            </a>
          </div>
        </template>
        <template v-else>
          <div class="ai-provider-form__api-key-row">
            <FormInput
              ref="apiKeyInput"
              v-model="values.api_key"
              :type="showApiKey ? 'text' : 'password'"
              autocomplete="off"
              class="ai-provider-form__api-key-input"
            />
            <a
              class="ai-provider-form__api-key-toggle"
              :title="showApiKey ? $t('aiProviderAdmin.hideApiKey') : $t('aiProviderAdmin.showApiKey')"
              @click="showApiKey = !showApiKey"
            >
              <i :class="showApiKey ? 'iconoir-eye-off' : 'iconoir-eye-empty'" />
            </a>
            <a
              v-if="provider"
              class="ai-provider-form__api-key-toggle"
              :title="$t('action.cancel')"
              @click="cancelEditApiKey"
            >
              <i class="iconoir-cancel" />
            </a>
          </div>
        </template>
      </FormGroup>

      <FormGroup
        v-if="hasExtraSetting('organization')"
        :label="$t('aiProviderAdmin.organization')"
        class="margin-bottom-2"
      >
        <FormInput v-model="extraSettings.organization" />
      </FormGroup>

      <FormGroup
        v-if="hasExtraSetting('base_url')"
        :label="$t('aiProviderAdmin.baseUrl')"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="extraSettings.base_url"
          placeholder="https://api.openai.com/v1"
        />
      </FormGroup>

      <FormGroup
        v-if="hasExtraSetting('host')"
        :label="$t('aiProviderAdmin.host')"
        :required="values.provider_type === 'ollama'"
        class="margin-bottom-2"
      >
        <FormInput
          v-model="extraSettings.host"
          placeholder="http://localhost:11434"
        />
      </FormGroup>

      <FormGroup :label="$t('aiProviderAdmin.models')" class="margin-bottom-2">
        <div class="ai-provider-form__models-list">
          <div
            v-for="(model, index) in modelRows"
            :key="index"
            class="ai-provider-form__model-card"
          >
            <div class="ai-provider-form__model-header">
              <FormInput
                v-model="model.model_identifier"
                :placeholder="$t('aiProviderAdmin.modelIdentifier')"
                class="ai-provider-form__model-input"
              />
              <a
                class="ai-provider-form__model-remove"
                :title="$t('action.delete')"
                @click="removeModel(index)"
              >
                <i class="iconoir-cancel" />
              </a>
            </div>

            <div class="ai-provider-form__model-features-section">
              <div class="ai-provider-form__model-features-header">
                <span class="ai-provider-form__model-features-label">
                  {{ $t('aiProviderAdmin.features') }}
                </span>
                <a class="ai-provider-form__model-features-action" @click="selectAllFeatures(model)">
                  {{ $t('aiProviderAdmin.selectAll') }}
                </a>
                <span class="ai-provider-form__model-features-sep">/</span>
                <a class="ai-provider-form__model-features-action" @click="selectNoFeatures(model)">
                  {{ $t('aiProviderAdmin.selectNone') }}
                </a>
              </div>
              <div class="ai-provider-form__model-features-list">
                <label
                  v-for="feature in orderedFeatures"
                  :key="feature.type"
                  class="ai-provider-form__model-feature"
                >
                  <input
                    type="checkbox"
                    :checked="model.features.includes(feature.type)"
                    @change="toggleFeature(model, feature.type)"
                  />
                  {{ feature.name }}
                </label>
              </div>
            </div>

            <div class="ai-provider-form__model-footer">
              <div class="ai-provider-form__model-status">
                <template v-if="!isModelDirty(model)">
                  <span
                    v-if="model.last_test_status === 'success'"
                    class="ai-provider-form__model-status-text ai-provider-form__model-status-text--success"
                  >
                    <i class="iconoir-check" /> {{ $t('aiProviderAdmin.testPassed') }}
                  </span>
                  <span
                    v-else-if="model.last_test_status === 'failure'"
                    class="ai-provider-form__model-status-text ai-provider-form__model-status-text--error"
                    :title="model.last_test_error"
                  >
                    <i class="iconoir-cancel" /> {{ model.last_test_error || $t('aiProviderAdmin.failed') }}
                  </span>
                  <span
                    v-else
                    class="ai-provider-form__model-status-text ai-provider-form__model-status-text--untested"
                  >
                    {{ $t('aiProviderAdmin.neverTested') }}
                  </span>
                </template>
                <span
                  v-else
                  class="ai-provider-form__model-status-text ai-provider-form__model-status-text--untested"
                >
                  {{ $t('aiProviderAdmin.neverTested') }}
                </span>
              </div>
              <a
                v-if="!isModelDirty(model) && model.id && model.model_identifier.trim()"
                class="ai-provider-form__model-test-link"
                :class="{ 'ai-provider-form__model-test-link--loading': testingModelId === model.id }"
                @click="onTestModel(model)"
              >
                {{ testingModelId === model.id ? $t('aiProviderAdmin.testing') : $t('aiProviderAdmin.test') }}
              </a>
              <span
                v-else-if="model.model_identifier.trim()"
                class="ai-provider-form__model-test-hint"
                :title="$t('aiProviderAdmin.saveToTest')"
              >
                {{ $t('aiProviderAdmin.test') }}
              </span>
            </div>
          </div>
        </div>
        <a class="ai-provider-form__add-model" @click="addModel">
          <i class="iconoir-plus" />
          {{ $t('aiProviderAdmin.addModel') }}
        </a>
      </FormGroup>

      <div class="actions">
        <ul class="action__links">
          <li>
            <a @click="hide()">{{ $t('action.cancel') }}</a>
          </li>
        </ul>
        <div class="ai-provider-form__actions">
          <Button
            type="secondary"
            :disabled="!isValid || loading"
            :loading="loading && saveMode === 'keep'"
            @click="submitAndKeepOpen"
          >
            {{ $t('aiProviderAdmin.save') }}
          </Button>
          <Button
            type="primary"
            :disabled="!isValid || loading"
            :loading="loading && saveMode === 'close'"
            @click="submitAndClose"
          >
            {{ $t('aiProviderAdmin.saveAndClose') }}
          </Button>
        </div>
      </div>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'

const PROVIDER_EXTRA_SETTINGS = {
  openai: ['organization', 'base_url'],
  anthropic: [],
  mistral: [],
  ollama: ['host'],
  openrouter: ['organization'],
}

const PROVIDER_TYPES = ['openai', 'anthropic', 'mistral', 'ollama', 'openrouter']

export default {
  name: 'AIProviderFormModal',
  mixins: [modal],
  props: {
    provider: {
      type: Object,
      default: null,
    },
    scope: {
      type: String,
      default: 'instance',
    },
    scopeId: {
      type: Number,
      default: null,
    },
  },
  data() {
    const p = this.provider
    const allFeatureTypes = this.getFeatureTypes().map((f) => f.type)
    return {
      loading: false,
      saveMode: null,
      savedProviderId: null,
      testingModelId: null,
      showApiKey: false,
      editingApiKey: false,
      values: {
        provider_type: p?.provider_type || 'openai',
        name: p?.name || '',
        api_key: '',
      },
      extraSettings: { ...(p?.extra_settings || {}) },
      modelRows: p?.models?.map((m) => ({
        id: m.id,
        model_identifier: m.model_identifier,
        savedIdentifier: m.model_identifier,
        features: [...(m.features || [])],
        last_test_status: m.last_test_status,
        last_test_error: m.last_test_error,
      })) || [{ model_identifier: '', features: [...allFeatureTypes] }],
    }
  },
  computed: {
    providerTypes() {
      return PROVIDER_TYPES
    },
    orderedFeatures() {
      return this.getFeatureTypes()
        .sort((a, b) => a.getOrder() - b.getOrder())
        .map((f) => ({ type: f.getType(), name: f.getName() }))
    },
    requiresApiKey() {
      return this.values.provider_type !== 'ollama'
    },
    isValid() {
      if (!this.values.name.trim() || !this.values.provider_type) {
        return false
      }
      // For new providers, API key is required (except Ollama)
      if (!this.provider && !this.savedProviderId && this.requiresApiKey) {
        if (!this.values.api_key.trim()) return false
      }
      // For editing, API key is only required if the user started replacing it
      if (this.editingApiKey && this.requiresApiKey) {
        if (!this.values.api_key.trim()) return false
      }
      // Ollama requires host
      if (this.values.provider_type === 'ollama') {
        if (!this.extraSettings.host?.trim()) return false
      }
      return true
    },
  },
  methods: {
    getFeatureTypes() {
      return Object.values(this.$registry.getAll('aiFeature'))
    },
    isModelDirty(model) {
      // A model is dirty if it's new (no id) or its name was edited
      if (!model.id) return true
      return model.model_identifier.trim() !== (model.savedIdentifier || '')
    },
    hasExtraSetting(key) {
      const type = this.values.provider_type
      const settings = PROVIDER_EXTRA_SETTINGS[type] || []
      return settings.includes(key)
    },
    addModel() {
      const allFeatureTypes = this.getFeatureTypes().map((f) => f.type)
      this.modelRows.push({ model_identifier: '', features: [...allFeatureTypes] })
    },
    removeModel(index) {
      this.modelRows.splice(index, 1)
    },
    toggleFeature(model, feature) {
      const idx = model.features.indexOf(feature)
      if (idx === -1) {
        model.features.push(feature)
      } else {
        model.features.splice(idx, 1)
      }
    },
    selectAllFeatures(model) {
      model.features = this.getFeatureTypes().map((f) => f.type)
    },
    selectNoFeatures(model) {
      model.features = []
    },
    startEditApiKey() {
      this.editingApiKey = true
      this.values.api_key = ''
      this.showApiKey = false
      this.$nextTick(() => {
        this.$refs.apiKeyInput?.$el?.querySelector('input')?.focus()
      })
    },
    cancelEditApiKey() {
      this.editingApiKey = false
      this.values.api_key = ''
      this.showApiKey = false
    },
    async onTestModel(model) {
      if (!model.id || this.testingModelId) return
      this.testingModelId = model.id
      try {
        // Use the store action so the list behind the modal updates too
        const result = await this.$store.dispatch('aiProvider/testModel', {
          modelId: model.id,
        })
        model.last_test_status = result.last_test_status
        model.last_test_error = result.last_test_error
      } catch (error) {
        notifyIf(error, 'aiProvider')
      } finally {
        this.testingModelId = null
      }
    },
    submitAndKeepOpen() {
      this.saveMode = 'keep'
      this._doSubmit(false)
    },
    submitAndClose() {
      this.saveMode = 'close'
      this._doSubmit(true)
    },
    async _doSubmit(closeAfter) {
      this.loading = true
      try {
        const payload = {
          provider_type: this.values.provider_type,
          name: this.values.name,
          extra_settings: this.extraSettings,
          models_data: this.modelRows
            .filter((m) => m.model_identifier.trim())
            .map((m) => ({
              model_identifier: m.model_identifier.trim(),
              features: m.features || [],
            })),
        }

        if (this.values.api_key) {
          payload.api_key = this.values.api_key
        }

        let result
        const providerId = this.savedProviderId || this.provider?.id
        if (providerId) {
          result = await this.$store.dispatch('aiProvider/update', {
            id: providerId,
            values: payload,
          })
        } else {
          result = await this.$store.dispatch('aiProvider/create', {
            values: payload,
            scope: this.scope,
            scopeId: this.scopeId,
          })
          // Remember the ID so subsequent saves are updates
          this.savedProviderId = result.id
        }

        // Merge server response into local rows. The backend preserves
        // models matched by identifier, so IDs and test status survive saves.
        if (result?.models) {
          this.modelRows = result.models.map((m) => ({
            id: m.id,
            model_identifier: m.model_identifier,
            savedIdentifier: m.model_identifier,
            features: [...(m.features || [])],
            last_test_status: m.last_test_status,
            last_test_error: m.last_test_error,
          }))
        }

        // Reset API key editing state after save
        this.editingApiKey = false
        this.values.api_key = ''

        if (closeAfter) {
          this.$emit(this.provider ? 'updated' : 'created')
          this.hide()
        } else {
          this.$store.dispatch('toast/success', {
            title: this.$t('aiProviderAdmin.saved'),
          })
        }
      } catch (error) {
        notifyIf(error, 'aiProvider')
      } finally {
        this.loading = false
        this.saveMode = null
      }
    },
  },
}
</script>
