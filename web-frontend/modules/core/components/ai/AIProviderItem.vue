<template>
  <div class="ai-provider-item" :class="{ 'ai-provider-item--disabled': !provider.is_enabled }">
    <div class="ai-provider-item__header" @click="expanded = !expanded">
      <i
        class="ai-provider-item__chevron"
        :class="expanded ? 'iconoir-nav-arrow-down' : 'iconoir-nav-arrow-right'"
      />
      <div class="ai-provider-item__info">
        <span class="ai-provider-item__name">{{ provider.name }}</span>
        <span class="ai-provider-item__meta">
          {{ provider.provider_type }} &middot;
          {{ provider.models.length }}
          {{ provider.models.length === 1 ? 'model' : 'models' }}
        </span>
      </div>
      <div class="ai-provider-item__actions" @click.stop>
        <SwitchInput
          v-if="!provider.is_own_scope"
          :value="provider.is_enabled"
          small
          @input="$emit('toggle', provider, $event)"
        />
        <template v-if="provider.is_own_scope">
          <a class="ai-provider-item__action" :title="$t('action.edit')" @click="$emit('edit', provider)">
            <i class="iconoir-edit-pencil" />
          </a>
          <a class="ai-provider-item__action ai-provider-item__action--danger" :title="$t('action.delete')" @click="$emit('delete', provider)">
            <i class="iconoir-bin" />
          </a>
        </template>
      </div>
    </div>

    <div v-if="expanded && provider.models.length > 0" class="ai-provider-item__models">
      <div
        v-for="model in provider.models"
        :key="model.id"
        class="ai-provider-item__model"
      >
        <div class="ai-provider-item__model-name">
          {{ model.display_name || model.model_identifier }}
        </div>
        <div class="ai-provider-item__model-features">
          <span
            v-for="feature in model.features"
            :key="feature"
            class="ai-provider-item__badge"
          >
            {{ getFeatureName(feature) }}
          </span>
          <span v-if="model.features.length === 0" class="ai-provider-item__no-features">
            {{ $t('aiProviderAdmin.noFeatures') }}
          </span>
        </div>
        <div class="ai-provider-item__model-status">
          <span v-if="model.last_test_status === 'success'" class="ai-provider-item__status ai-provider-item__status--success">
            <i class="iconoir-check" /> {{ timeAgo(model.last_test_at) }}
          </span>
          <span
            v-else-if="model.last_test_status === 'failure'"
            class="ai-provider-item__status ai-provider-item__status--error"
            :title="model.last_test_error"
          >
            <i class="iconoir-cancel" /> {{ $t('aiProviderAdmin.failed') }}
          </span>
          <span v-else class="ai-provider-item__status ai-provider-item__status--untested">
            &mdash;
          </span>
        </div>
        <div class="ai-provider-item__model-test">
          <Button
            size="small"
            type="secondary"
            :loading="testingModelId === model.id"
            :disabled="testingModelId !== null"
            @click="onTestModel(model)"
          >
            {{ $t('aiProviderAdmin.test') }}
          </Button>
        </div>
      </div>
    </div>

    <div v-if="expanded && provider.models.length === 0" class="ai-provider-item__empty">
      {{ $t('aiProviderAdmin.noModels') }}
    </div>
  </div>
</template>

<script>
import SwitchInput from '@baserow/modules/core/components/SwitchInput.vue'

export default {
  name: 'AIProviderItem',
  components: { SwitchInput },
  props: {
    provider: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      expanded: true,
      testingModelId: null,
    }
  },
  methods: {
    getFeatureName(featureType) {
      try {
        return this.$registry.get('aiFeature', featureType).getName()
      } catch {
        return featureType
      }
    },
    async onTestModel(model) {
      this.testingModelId = model.id
      try {
        await this.$emit('test-model', model.id)
      } finally {
        setTimeout(() => {
          this.testingModelId = null
        }, 500)
      }
    },
    timeAgo(dateStr) {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      const now = new Date()
      const diff = Math.floor((now - date) / 1000)
      if (diff < 60) return 'just now'
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return `${Math.floor(diff / 86400)}d ago`
    },
  },
}
</script>
