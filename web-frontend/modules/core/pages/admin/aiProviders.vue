<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <div class="ai-provider-admin">
      <div class="ai-provider-admin__header">
        <h1>{{ $t('aiProviderAdmin.title') }}</h1>
        <Button icon="iconoir-plus" @click="openCreateModal">
          {{ $t('aiProviderAdmin.addProvider') }}
        </Button>
      </div>

      <p class="ai-provider-admin__description">
        {{ $t('aiProviderAdmin.description') }}
      </p>

      <div v-if="!loaded || loading" class="ai-provider-admin__loading">
        <div class="loading"></div>
      </div>

      <template v-else-if="providers.length === 0">
        <div class="placeholder">
          <div class="placeholder__icon">
            <i class="iconoir-sparks"></i>
          </div>
          <h2 class="placeholder__title">
            {{ $t('aiProviderAdmin.noProviders') }}
          </h2>
          <p class="placeholder__content">
            {{ $t('aiProviderAdmin.noProvidersDescription') }}
          </p>
        </div>
      </template>

      <div v-else class="ai-provider-admin__list">
        <AIProviderItem
          v-for="provider in providers"
          :key="provider.id"
          :provider="provider"
          @edit="openEditModal"
          @delete="openDeleteModal"
          @test-model="testModel"
        />
      </div>

      <AIProviderFormModal
        v-if="showCreate"
        ref="createModal"
        @created="showCreate = false"
        @hidden="showCreate = false"
      />

      <AIProviderFormModal
        v-if="editingProvider"
        ref="editModal"
        :provider="editingProvider"
        @updated="editingProvider = null"
        @hidden="editingProvider = null"
      />

      <AIProviderDeleteModal
        v-if="deletingProvider"
        ref="deleteModal"
        :provider="deletingProvider"
        @deleted="deletingProvider = null"
        @hidden="deletingProvider = null"
      />
    </div>
  </div>
</template>

<script>
import AIProviderItem from '@baserow/modules/core/components/ai/AIProviderItem'
import AIProviderFormModal from '@baserow/modules/core/components/ai/AIProviderFormModal'
import AIProviderDeleteModal from '@baserow/modules/core/components/ai/AIProviderDeleteModal'

export default {
  name: 'AdminAIProviders',
  components: { AIProviderItem, AIProviderFormModal, AIProviderDeleteModal },
  layout: 'app',
  middleware: 'staff',
  data() {
    return {
      showCreate: false,
      editingProvider: null,
      deletingProvider: null,
    }
  },
  computed: {
    providers() {
      return this.$store.getters['aiProvider/getAll']
    },
    loading() {
      return this.$store.getters['aiProvider/isLoading']
    },
    loaded() {
      return this.$store.getters['aiProvider/isLoaded']
    },
  },
  async mounted() {
    await this.$store.dispatch('aiProvider/fetchAll', {
      scope: 'instance',
    })
  },
  methods: {
    openCreateModal() {
      this.showCreate = true
      this.$nextTick(() => {
        this.$refs.createModal.show()
      })
    },
    openEditModal(provider) {
      this.editingProvider = provider
      this.$nextTick(() => {
        this.$refs.editModal.show()
      })
    },
    openDeleteModal(provider) {
      this.deletingProvider = provider
      this.$nextTick(() => {
        this.$refs.deleteModal.show()
      })
    },
    async testModel(modelId) {
      try {
        await this.$store.dispatch('aiProvider/testModel', { modelId })
      } catch (error) {
        this.$store.dispatch('toast/error', {
          title: this.$t('aiProviderAdmin.testError'),
        })
      }
    },
  },
}
</script>
