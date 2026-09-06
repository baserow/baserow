<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <main class="ai-provider-admin">
      <header class="ai-provider-admin__header">
        <div>
          <h1>{{ $t('aiProviderAdmin.title') }}</h1>
          <p>{{ $t('aiProviderAdmin.description') }}</p>
        </div>
        <Button
          icon="iconoir-plus"
          :disabled="availableProviderTypes.length === 0"
          @click="openProviderForm(null)"
        >
          {{ $t('aiProviderAdmin.addProvider') }}
        </Button>
      </header>

      <AIProviderFeatureSettings
        v-if="loaded && !loading && !initialLoadFailed"
      />

      <AIProviderAdminSkeleton
        v-if="loading || (!loaded && !initialLoadFailed)"
      />
      <div v-else-if="initialLoadFailed && !loaded" class="placeholder">
        <div class="placeholder__icon">
          <i class="iconoir-warning-circle" />
        </div>
        <h2 class="placeholder__title">
          {{ $t('aiProviderAdmin.loadError') }}
        </h2>
        <p class="placeholder__content">
          {{ $t('aiProviderAdmin.loadErrorDescription') }}
        </p>
        <Button type="secondary" @click="loadProviders">
          {{ $t('aiProviderAdmin.retry') }}
        </Button>
      </div>
      <div v-else-if="providers.length === 0" class="placeholder">
        <div class="placeholder__icon"><i class="iconoir-sparks" /></div>
        <h2 class="placeholder__title">
          {{ $t('aiProviderAdmin.noProviders') }}
        </h2>
        <p class="placeholder__content">
          {{ $t('aiProviderAdmin.noProvidersDescription') }}
        </p>
      </div>
      <div v-else class="ai-provider-admin__list">
        <AIProviderItem
          v-for="provider in providers"
          :key="provider.id"
          :provider="provider"
          :provider-type="providerType(provider.provider_type)"
          :testing-model-ids="testingModelIds"
          @edit-provider="openProviderForm"
          @toggle-provider="toggleProvider"
          @delete-provider="deleteProvider"
          @add-model="openModelForm"
          @test-all-models="testAllModels"
          @edit-model="openModelForm"
          @toggle-model="toggleModel"
          @delete-model="deleteModel"
          @test-model="testModel"
        />
      </div>

      <AIProviderFormModal
        v-if="providerFormOpen"
        ref="providerForm"
        :provider="editingProvider"
        :provider-types="formProviderTypes"
        @hidden="providerFormOpen = false"
        @saved="providerFormOpen = false"
      />
      <AIProviderModelFormModal
        v-if="modelFormOpen"
        ref="modelForm"
        :provider="editingModelProvider"
        :model="editingModel"
        @hidden="modelFormOpen = false"
        @saved="modelFormOpen = false"
      />
      <AIProviderConfirmModal
        v-if="pendingAction"
        ref="confirmModal"
        :title="pendingAction.title"
        :message="pendingAction.message"
        :confirm-label="pendingAction.confirmLabel"
        :danger="pendingAction.danger"
        :loading="actionLoading"
        @hidden="pendingAction = null"
        @confirm="confirmPendingAction"
      />
    </main>
  </div>
</template>

<script>
import { useHead } from '#imports'
import { useNuxtApp } from '#app'

import AIProviderAdminSkeleton from '@baserow/modules/core/components/ai/AIProviderAdminSkeleton'
import AIProviderConfirmModal from '@baserow/modules/core/components/ai/AIProviderConfirmModal'
import AIProviderFeatureSettings from '@baserow/modules/core/components/ai/AIProviderFeatureSettings'
import AIProviderFormModal from '@baserow/modules/core/components/ai/AIProviderFormModal'
import AIProviderItem from '@baserow/modules/core/components/ai/AIProviderItem'
import AIProviderModelFormModal from '@baserow/modules/core/components/ai/AIProviderModelFormModal'
import { aiProviderErrorMessage } from '@baserow/modules/core/utils/aiProvider'

export default {
  name: 'AdminAIProviders',
  components: {
    AIProviderAdminSkeleton,
    AIProviderConfirmModal,
    AIProviderFeatureSettings,
    AIProviderFormModal,
    AIProviderItem,
    AIProviderModelFormModal,
  },
  layout: 'app',
  middleware: ['staff', 'aiProvidersFeatureFlag'],
  setup() {
    const { $i18n } = useNuxtApp()
    useHead({ title: $i18n.t('aiProviderAdmin.title') })
  },
  data() {
    return {
      providerFormOpen: false,
      editingProvider: null,
      modelFormOpen: false,
      editingModelProvider: null,
      editingModel: null,
      pendingAction: null,
      actionLoading: false,
      testingModelIds: [],
      initialLoadFailed: false,
    }
  },
  computed: {
    providers() {
      return this.$store.getters['aiProvider/getAll'](null)
    },
    providerTypes() {
      return this.$store.getters['aiProvider/getTypes'](null)
    },
    loading() {
      return this.$store.getters['aiProvider/isLoading']
    },
    loaded() {
      return this.$store.getters['aiProvider/isLoaded'](null)
    },
    availableProviderTypes() {
      const configuredTypes = new Set(
        this.providers.map((provider) => provider.provider_type)
      )
      return this.providerTypes.filter(
        (providerType) => !configuredTypes.has(providerType.type)
      )
    },
    formProviderTypes() {
      if (!this.editingProvider) return this.availableProviderTypes
      return this.providerTypes.filter(
        (providerType) =>
          providerType.type === this.editingProvider.provider_type
      )
    },
  },
  async mounted() {
    await this.loadProviders()
  },
  methods: {
    async loadProviders() {
      this.initialLoadFailed = false
      try {
        await this.$store.dispatch('aiProvider/fetchInitial')
      } catch {
        this.initialLoadFailed = true
        this.$store.dispatch('toast/error', {
          title: this.$t('aiProviderAdmin.loadError'),
        })
      }
    },
    providerType(type) {
      return this.providerTypes.find(
        (providerType) => providerType.type === type
      )
    },
    providerDisplayName(provider) {
      return (
        this.providerType(provider.provider_type)?.name ||
        provider.provider_type
      )
    },
    openProviderForm(provider) {
      this.editingProvider = provider
      this.providerFormOpen = true
      this.$nextTick(() => this.$refs.providerForm.show())
    },
    openModelForm(provider, model = null) {
      this.editingModelProvider = provider
      this.editingModel = model
      this.modelFormOpen = true
      this.$nextTick(() => this.$refs.modelForm.show())
    },
    async toggleProvider(provider) {
      return await this.runAction(
        provider.is_active ? 'provider-disable' : 'provider-enable',
        provider
      )
    },
    deleteProvider(provider) {
      this.openConfirmation({
        kind: 'provider-delete',
        resource: provider,
        title: this.$t('aiProviderAdmin.deleteProviderTitle', {
          name: this.providerDisplayName(provider),
        }),
        message: this.$t('aiProviderAdmin.deleteProviderDescription'),
        confirmLabel: this.$t('action.delete'),
        danger: true,
      })
    },
    async toggleModel(model) {
      return await this.runAction(
        model.is_enabled ? 'model-disable' : 'model-enable',
        model
      )
    },
    deleteModel(model) {
      this.openConfirmation({
        kind: 'model-delete',
        resource: model,
        title: this.$t('aiProviderAdmin.deleteModelTitle', {
          name: model.model_identifier,
        }),
        message: this.$t('aiProviderAdmin.deleteModelDescription'),
        confirmLabel: this.$t('action.delete'),
        danger: true,
      })
    },
    testModel(model) {
      return this.runAction('model-test', model)
    },
    testAllModels(provider) {
      return this.runAction('provider-models-test', provider)
    },
    openConfirmation(action) {
      this.pendingAction = action
      this.$nextTick(() => this.$refs.confirmModal.show())
    },
    async confirmPendingAction() {
      const action = this.pendingAction
      this.actionLoading = true
      try {
        const succeeded = await this.runAction(action.kind, action.resource)
        if (succeeded) this.$refs.confirmModal.hide()
      } finally {
        this.actionLoading = false
      }
    },
    async runAction(kind, resource) {
      const modelIdsUnderTest =
        kind === 'model-test'
          ? [resource.id]
          : kind === 'provider-models-test'
            ? resource.models.map((model) => model.id)
            : []
      if (modelIdsUnderTest.length) {
        this.testingModelIds = [
          ...new Set([...this.testingModelIds, ...modelIdsUnderTest]),
        ]
      }

      try {
        if (kind === 'provider-enable' || kind === 'provider-disable') {
          await this.$store.dispatch('aiProvider/update', {
            providerId: resource.id,
            values: {
              is_active: kind === 'provider-enable',
            },
          })
        } else if (kind === 'provider-delete') {
          await this.$store.dispatch('aiProvider/delete', resource.id)
        } else if (kind === 'model-enable' || kind === 'model-disable') {
          await this.$store.dispatch('aiProvider/updateModel', {
            modelId: resource.id,
            values: {
              is_enabled: kind === 'model-enable',
            },
          })
        } else if (kind === 'model-delete') {
          await this.$store.dispatch('aiProvider/deleteModel', resource.id)
        } else if (kind === 'model-test') {
          await this.$store.dispatch('aiProvider/testModels', {
            model_ids: [resource.id],
          })
        } else if (kind === 'provider-models-test') {
          await this.$store.dispatch('aiProvider/testModels', {
            model_ids: resource.models.map((model) => model.id),
          })
        }
        return true
      } catch (error) {
        this.showActionError(error)
        return false
      } finally {
        if (modelIdsUnderTest.length) {
          this.testingModelIds = this.testingModelIds.filter(
            (modelId) => !modelIdsUnderTest.includes(modelId)
          )
        }
      }
    },
    showActionError(error) {
      this.$store.dispatch('toast/error', {
        title: this.$t('aiProviderAdmin.actionError'),
        message: aiProviderErrorMessage(error),
      })
    },
  },
}
</script>
