<template>
  <section
    class="ai-provider-card"
    :class="{ 'ai-provider-card--inactive': !provider.is_active }"
  >
    <header class="ai-provider-card__header">
      <div class="ai-provider-card__heading">
        <div class="ai-provider-card__title-row">
          <h2 class="ai-provider-card__title">
            {{ providerType?.name || provider.provider_type }}
          </h2>
          <Badge :color="provider.is_active ? 'green' : 'neutral'">
            {{
              provider.is_active
                ? $t('aiProviderAdmin.active')
                : $t('aiProviderAdmin.inactive')
            }}
          </Badge>
        </div>
      </div>
      <div class="ai-provider-card__actions">
        <Button
          type="secondary"
          size="small"
          icon="iconoir-plus"
          :disabled="providerTestRunning"
          @click="$emit('add-model', provider)"
        >
          {{ $t('aiProviderAdmin.addModel') }}
        </Button>
        <Button
          type="secondary"
          size="small"
          :disabled="provider.models.length === 0 || providerTestRunning"
          :title="$t('aiProviderAdmin.testAllModelsButtonTitle')"
          @click="$emit('test-all-models', provider)"
        >
          {{ $t('aiProviderAdmin.test') }}
        </Button>
        <Button
          type="secondary"
          size="small"
          :disabled="providerTestRunning"
          @click="$emit('edit-provider', provider)"
        >
          {{ $t('action.edit') }}
        </Button>
        <Button
          type="secondary"
          size="small"
          :disabled="providerTestRunning"
          @click="$emit('toggle-provider', provider)"
        >
          {{
            provider.is_active
              ? $t('aiProviderAdmin.disable')
              : $t('aiProviderAdmin.enable')
          }}
        </Button>
        <Button
          type="danger"
          size="small"
          icon="iconoir-bin"
          :disabled="providerTestRunning"
          :aria-label="$t('action.delete')"
          :title="$t('action.delete')"
          @click="$emit('delete-provider', provider)"
        />
      </div>
    </header>

    <div v-if="provider.models.length" class="ai-provider-card__models">
      <div
        v-for="model in provider.models"
        :key="model.id"
        class="ai-provider-model"
        :class="{ 'ai-provider-model--inactive': !model.is_enabled }"
      >
        <div
          class="ai-provider-model__identity"
          :class="{
            'ai-provider-model__identity--inactive': !model.is_enabled,
          }"
        >
          <div class="ai-provider-model__name-row">
            <strong>{{ model.model_identifier }}</strong>
            <Badge v-if="!model.is_enabled" color="neutral">
              {{ $t('aiProviderAdmin.modelDisabled') }}
            </Badge>
          </div>
        </div>
        <div class="ai-provider-model__status">
          <span
            v-if="model.last_test_status === 'success'"
            class="color-success"
          >
            <i class="iconoir-check-circle" />
            {{ $t('aiProviderAdmin.testPassed') }}
          </span>
          <template v-else-if="model.last_test_status === 'failure'">
            <span class="color-error">
              <i class="iconoir-warning-circle" />
              {{ $t('aiProviderAdmin.testFailed') }}
            </span>
            <span
              v-if="model.last_test_error"
              v-tooltip:[tooltipOptions]="model.last_test_error"
              class="ai-provider-model__error"
            >
              {{ model.last_test_error }}
            </span>
          </template>
          <span v-else>{{ $t('aiProviderAdmin.notTested') }}</span>
        </div>
        <div class="ai-provider-model__actions">
          <Button
            type="secondary"
            size="small"
            :loading="isModelTesting(model)"
            :title="$t('aiProviderAdmin.testModelButtonTitle')"
            @click="$emit('test-model', model)"
          >
            {{ $t('aiProviderAdmin.test') }}
          </Button>
          <Button
            type="secondary"
            size="small"
            :disabled="isModelTesting(model)"
            @click="$emit('edit-model', provider, model)"
          >
            {{ $t('action.edit') }}
          </Button>
          <Button
            type="secondary"
            size="small"
            :disabled="isModelTesting(model)"
            @click="$emit('toggle-model', model)"
          >
            {{
              model.is_enabled
                ? $t('aiProviderAdmin.disable')
                : $t('aiProviderAdmin.enable')
            }}
          </Button>
          <Button
            type="danger"
            size="small"
            icon="iconoir-bin"
            :disabled="isModelTesting(model)"
            :aria-label="$t('action.delete')"
            :title="$t('action.delete')"
            @click="$emit('delete-model', model)"
          />
        </div>
      </div>
    </div>
    <p v-else class="ai-provider-card__empty">
      {{ $t('aiProviderAdmin.noModels') }}
    </p>
  </section>
</template>

<script>
export default {
  name: 'AIProviderItem',
  props: {
    provider: { type: Object, required: true },
    providerType: { type: Object, default: null },
    testingModelIds: { type: Array, default: () => [] },
  },
  emits: [
    'edit-provider',
    'toggle-provider',
    'delete-provider',
    'add-model',
    'test-all-models',
    'edit-model',
    'toggle-model',
    'delete-model',
    'test-model',
  ],
  data() {
    return {
      tooltipOptions: {
        duration: 2,
        contentClasses: [
          'tooltip__content--expandable',
          'tooltip__content--expandable-plain-text',
        ],
      },
    }
  },
  computed: {
    providerTestRunning() {
      return this.provider.models.some((model) => this.isModelTesting(model))
    },
  },
  methods: {
    isModelTesting(model) {
      return this.testingModelIds.includes(model.id)
    },
  },
}
</script>
