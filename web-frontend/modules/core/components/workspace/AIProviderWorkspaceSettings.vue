<template>
  <div class="ai-provider-workspace-settings">
    <header class="ai-provider-admin__header">
      <div>
        <h2 class="box__title">
          {{ $t('generativeAIWorkspaceSettings.providerTitle') }}
        </h2>
        <p>{{ $t('generativeAIWorkspaceSettings.providerDescription') }}</p>
      </div>
    </header>

    <div
      v-if="loaded && !loading && !initialLoadFailed"
      class="ai-provider-workspace-settings__toolbar"
    >
      <Button
        icon="iconoir-plus"
        :disabled="availableProviderTypes.length === 0"
        @click="openProviderForm(null)"
      >
        {{ $t('aiProviderAdmin.addProvider') }}
      </Button>
    </div>

    <div
      v-if="loading || (!loaded && !initialLoadFailed)"
      class="ai-provider-admin__loading"
    >
      <div class="loading" />
    </div>
    <div v-else-if="initialLoadFailed" class="placeholder">
      <div class="placeholder__icon"><i class="iconoir-warning-circle" /></div>
      <h2 class="placeholder__title">{{ $t('aiProviderAdmin.loadError') }}</h2>
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
        {{ $t('generativeAIWorkspaceSettings.noProviders') }}
      </h2>
      <p class="placeholder__content">
        {{ $t('generativeAIWorkspaceSettings.noProvidersDescription') }}
      </p>
    </div>
    <div v-else class="ai-provider-admin__list">
      <section
        v-for="group in providerGroups"
        :key="group.providerType"
        class="ai-provider-hierarchy"
      >
        <header
          v-if="!group.workspaceProvider"
          class="ai-provider-hierarchy__header"
        >
          <h2 class="ai-provider-hierarchy__title">
            {{ providerDisplayName(group.primaryProvider) }}
          </h2>
          <Button
            type="secondary"
            size="small"
            icon="iconoir-plus"
            @click="openProviderForm(null, group.providerType)"
          >
            {{ $t('generativeAIWorkspaceSettings.addWorkspaceConfiguration') }}
          </Button>
        </header>

        <div
          class="ai-provider-hierarchy__layers"
          :class="{
            'ai-provider-hierarchy__layers--with-header':
              !group.workspaceProvider,
          }"
        >
          <AIProviderItem
            v-if="group.workspaceProvider"
            :provider="group.workspaceProvider"
            :provider-type="providerType(group.providerType)"
            :testing-model-ids="testingModelIds"
            :embedded="true"
            :primary="true"
            :title="providerDisplayName(group.workspaceProvider)"
            :hide-active-status="true"
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
          <AIProviderItem
            v-if="group.inheritedProvider"
            :provider="group.inheritedProvider"
            :provider-type="providerType(group.providerType)"
            :testing-model-ids="testingModelIds"
            :embedded="true"
            :title="$t('generativeAIWorkspaceSettings.sharedModelsTitle')"
            :source-label="$t('aiProviderAdmin.inherited')"
            source-color="cyan"
            :hide-active-status="true"
            :model-annotations="inheritedModelAnnotations(group)"
            :status-label="inheritedStatusLabel(group.inheritedProvider)"
            @toggle-provider="toggleProvider"
          />
        </div>
      </section>
    </div>

    <AIProviderFormModal
      v-if="providerFormOpen"
      ref="providerForm"
      :provider="editingProvider"
      :provider-types="formProviderTypes"
      :workspace-id="workspace.id"
      @hidden="providerFormOpen = false"
      @saved="providerSaved"
    />
    <AIProviderModelFormModal
      v-if="modelFormOpen"
      ref="modelForm"
      :provider="editingModelProvider"
      :model="editingModel"
      :workspace-id="workspace.id"
      @hidden="modelFormOpen = false"
      @saved="modelSaved"
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
  </div>
</template>

<script>
import AIProviderConfirmModal from '@baserow/modules/core/components/ai/AIProviderConfirmModal'
import AIProviderFormModal from '@baserow/modules/core/components/ai/AIProviderFormModal'
import AIProviderItem from '@baserow/modules/core/components/ai/AIProviderItem'
import AIProviderModelFormModal from '@baserow/modules/core/components/ai/AIProviderModelFormModal'
import WorkspaceService from '@baserow/modules/core/services/workspace'

export default {
  name: 'AIProviderWorkspaceSettings',
  components: {
    AIProviderConfirmModal,
    AIProviderFormModal,
    AIProviderItem,
    AIProviderModelFormModal,
  },
  props: {
    workspace: { type: Object, required: true },
  },
  data() {
    return {
      providerFormOpen: false,
      editingProvider: null,
      creatingProviderType: null,
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
      return this.$store.getters['aiProvider/getAll'](this.workspace.id)
    },
    providerGroups() {
      const groups = new Map()
      for (const provider of this.providers) {
        const group = groups.get(provider.provider_type) || {
          providerType: provider.provider_type,
          inheritedProvider: null,
          workspaceProvider: null,
          primaryProvider: provider,
        }
        if (provider.read_only) group.inheritedProvider = provider
        else group.workspaceProvider = provider
        groups.set(provider.provider_type, group)
      }
      return [...groups.values()]
    },
    providerTypes() {
      return this.$store.getters['aiProvider/getTypes'](this.workspace.id)
    },
    loading() {
      return this.$store.getters['aiProvider/isLoading']
    },
    loaded() {
      return this.$store.getters['aiProvider/isLoaded'](this.workspace.id)
    },
    availableProviderTypes() {
      const ownedTypes = new Set(
        this.providers
          .filter((provider) => !provider.read_only)
          .map((provider) => provider.provider_type)
      )
      return this.providerTypes.filter(
        (providerType) => !ownedTypes.has(providerType.type)
      )
    },
    formProviderTypes() {
      if (this.creatingProviderType) {
        return this.availableProviderTypes.filter(
          (providerType) => providerType.type === this.creatingProviderType
        )
      }
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
        await this.$store.dispatch('aiProvider/fetchInitial', {
          workspaceId: this.workspace.id,
        })
      } catch {
        this.initialLoadFailed = true
      }
    },
    async refreshWorkspace() {
      try {
        const { data } = await WorkspaceService(this.$client).fetchAll()
        const workspace = data.find((item) => item.id === this.workspace.id)
        if (workspace) {
          await this.$store.dispatch('workspace/forceUpdate', {
            workspace: this.workspace,
            values: workspace,
          })
        }
      } catch {
        return
      }
    },
    async providerSaved() {
      this.providerFormOpen = false
      await this.loadProviders()
      await this.refreshWorkspace()
    },
    async modelSaved() {
      this.modelFormOpen = false
      await this.refreshWorkspace()
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
    inheritedModelAnnotations(group) {
      const overriddenIdentifiers = new Set(
        group.workspaceProvider?.is_active
          ? group.workspaceProvider.models.map(
              (model) => model.model_identifier
            )
          : []
      )
      return Object.fromEntries(
        group.inheritedProvider.models
          .filter((model) => overriddenIdentifiers.has(model.model_identifier))
          .map((model) => [
            model.id,
            {
              label: this.$t('generativeAIWorkspaceSettings.overridden'),
              tooltip: this.$t(
                'generativeAIWorkspaceSettings.overriddenByWorkspace'
              ),
              muted: true,
            },
          ])
      )
    },
    inheritedStatusLabel(provider) {
      return provider.workspace_enabled
        ? ''
        : this.$t('generativeAIWorkspaceSettings.disabledInWorkspace')
    },
    openProviderForm(provider, providerType = null) {
      if (provider?.read_only) return
      this.editingProvider = provider
      this.creatingProviderType = providerType
      this.providerFormOpen = true
      this.$nextTick(() => this.$refs.providerForm.show())
    },
    openModelForm(provider, model = null) {
      if (provider.read_only) return
      this.editingModelProvider = provider
      this.editingModel = model
      this.modelFormOpen = true
      this.$nextTick(() => this.$refs.modelForm.show())
    },
    toggleProvider(provider) {
      const enabled = provider.read_only
        ? provider.workspace_enabled
        : provider.is_active
      return this.runAction(
        enabled ? 'provider-disable' : 'provider-enable',
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
    toggleModel(model) {
      return this.runAction(
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

      const workspaceId = this.workspace.id
      try {
        if (kind === 'provider-enable' || kind === 'provider-disable') {
          await this.$store.dispatch('aiProvider/update', {
            providerId: resource.id,
            workspaceId,
            values: { is_active: kind === 'provider-enable' },
          })
        } else if (kind === 'provider-delete') {
          await this.$store.dispatch('aiProvider/delete', {
            providerId: resource.id,
            workspaceId,
          })
        } else if (kind === 'model-enable' || kind === 'model-disable') {
          await this.$store.dispatch('aiProvider/updateModel', {
            modelId: resource.id,
            workspaceId,
            values: { is_enabled: kind === 'model-enable' },
          })
        } else if (kind === 'model-delete') {
          await this.$store.dispatch('aiProvider/deleteModel', {
            modelId: resource.id,
            workspaceId,
          })
        } else if (kind === 'model-test') {
          await this.$store.dispatch('aiProvider/testModels', {
            workspaceId,
            values: { model_ids: [resource.id] },
          })
        } else if (kind === 'provider-models-test') {
          await this.$store.dispatch('aiProvider/testModels', {
            workspaceId,
            values: { model_ids: resource.models.map((model) => model.id) },
          })
        }
        if (!modelIdsUnderTest.length) {
          if (kind === 'provider-delete') {
            await this.loadProviders()
          }
          await this.refreshWorkspace()
        }
        return true
      } catch (error) {
        this.$store.dispatch('toast/error', {
          title: this.$t('aiProviderAdmin.actionError'),
          message:
            error.response?.data?.detail?.message ||
            error.response?.data?.detail,
        })
        return false
      } finally {
        if (modelIdsUnderTest.length) {
          this.testingModelIds = this.testingModelIds.filter(
            (modelId) => !modelIdsUnderTest.includes(modelId)
          )
        }
      }
    },
  },
}
</script>
