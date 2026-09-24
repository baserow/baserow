<template>
  <section
    class="ai-provider-card"
    :class="{
      'ai-provider-card--inactive': !provider.is_active,
      'ai-provider-card--embedded': embedded,
      'ai-provider-card--primary': primary,
    }"
  >
    <header class="ai-provider-card__header">
      <div class="ai-provider-card__heading">
        <div class="ai-provider-card__title-row">
          <component
            :is="primary || !embedded ? 'h2' : 'h3'"
            class="ai-provider-card__title"
          >
            {{ title || providerType?.name || provider.provider_type }}
          </component>
          <Badge v-if="sourceLabel" :color="sourceColor" bold>
            {{ sourceLabel }}
          </Badge>
          <Badge v-else-if="provider.read_only" color="cyan" bold>
            {{ $t('aiProviderAdmin.inherited') }}
          </Badge>
          <Badge
            v-if="showStatusBadge"
            :color="provider.is_active ? 'green' : 'neutral'"
          >
            {{ providerStatusLabel }}
          </Badge>
        </div>
      </div>
      <div class="ai-provider-card__actions">
        <AIProviderActionsMenu
          :actions="providerMenuActions"
          :disabled="providerTestRunning"
          :title="$t('aiProviderAdmin.moreActions')"
          @select="onProviderAction"
        />
      </div>
    </header>

    <div v-if="provider.models.length" class="ai-provider-card__models">
      <div
        v-for="model in provider.models"
        :key="model.id"
        class="ai-provider-model"
        :class="{
          'ai-provider-model--inactive': !model.is_enabled,
          'ai-provider-model--overridden': modelAnnotation(model)?.muted,
        }"
      >
        <div class="ai-provider-model__identity">
          <span
            class="ai-provider-model__name"
            :class="{ 'ai-provider-model__name--inactive': !model.is_enabled }"
          >
            {{ model.model_identifier }}
          </span>
          <span class="ai-provider-model__features">
            {{ featureSummary(model) }}
          </span>
        </div>
        <div class="ai-provider-model__badges">
          <Badge
            v-if="!model.is_enabled"
            class="ai-provider-model__disabled-badge"
            color="neutral"
            bold
          >
            {{ $t('aiProviderAdmin.modelDisabled') }}
          </Badge>
          <Badge
            v-if="modelAnnotation(model)"
            v-tooltip="modelAnnotation(model).tooltip"
            class="ai-provider-model__annotation-badge"
            color="yellow"
            bold
            :aria-label="modelAnnotation(model).tooltip"
          >
            {{ modelAnnotation(model).label }}
          </Badge>
        </div>
        <div class="ai-provider-model__status" role="status" aria-live="polite">
          <span v-if="isModelTesting(model)" class="ai-provider-model__testing">
            {{ $t('aiProviderAdmin.testing') }}
          </span>
          <span
            v-else-if="model.last_test_status === 'success'"
            class="color-success"
          >
            <i class="iconoir-check-circle" />
            {{ $t('aiProviderAdmin.testPassed') }}
          </span>
          <template v-else-if="model.last_test_status === 'failure'">
            <span
              v-tooltip:[tooltipOptions]="modelTestTooltip(model)"
              class="ai-provider-model__test-failed color-error"
            >
              <i class="iconoir-warning-circle" />
              {{ modelTestFailureLabel(model) }}
            </span>
          </template>
          <span v-else>{{ $t('aiProviderAdmin.notTested') }}</span>
        </div>
        <div class="ai-provider-model__actions">
          <AIProviderActionsMenu
            :actions="modelMenuActions(model)"
            :disabled="isModelTesting(model) || isModelOverridden(model)"
            :show-disabled-trigger="isModelOverridden(model)"
            :title="modelActionsTitle(model)"
            @select="onModelAction($event, model)"
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
import AIProviderActionsMenu from '@baserow/modules/core/components/ai/AIProviderActionsMenu'

export default {
  name: 'AIProviderItem',
  components: { AIProviderActionsMenu },
  props: {
    provider: { type: Object, required: true },
    providerType: { type: Object, default: null },
    testingModelIds: { type: Array, default: () => [] },
    embedded: { type: Boolean, default: false },
    primary: { type: Boolean, default: false },
    title: { type: String, default: '' },
    sourceLabel: { type: String, default: '' },
    sourceColor: { type: String, default: 'neutral' },
    hideActiveStatus: { type: Boolean, default: false },
    modelAnnotations: { type: Object, default: () => ({}) },
    statusLabel: { type: String, default: '' },
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
    providerToggleState() {
      return this.provider.read_only
        ? this.provider.workspace_enabled
        : this.provider.is_active
    },
    showStatusBadge() {
      return !this.hideActiveStatus || !this.provider.is_active
    },
    providerStatusLabel() {
      if (this.statusLabel) return this.statusLabel
      return this.provider.is_active
        ? this.$t('aiProviderAdmin.active')
        : this.$t('aiProviderAdmin.inactive')
    },
    toggleAction() {
      return {
        key: 'toggle',
        label: this.toggleActionTitle(this.providerToggleState),
        icon: this.toggleActionIcon(this.providerToggleState),
      }
    },
    providerMenuActions() {
      // The instance owns it; a workspace can only toggle its own use of it.
      if (this.provider.read_only) {
        return this.provider.models.length ? [this.toggleAction] : []
      }
      const actions = [
        {
          key: 'add-model',
          label: this.$t('aiProviderAdmin.addModel'),
          icon: 'iconoir-plus',
        },
      ]
      if (this.provider.models.length > 0) {
        actions.push({
          key: 'test',
          label: this.$t('aiProviderAdmin.testAllModels'),
          icon: 'iconoir-play',
        })
      }
      actions.push(
        {
          key: 'edit',
          label: this.$t('action.edit'),
          icon: 'iconoir-edit',
        },
        this.toggleAction,
        {
          key: 'delete',
          label: this.$t('action.delete'),
          icon: 'iconoir-bin',
          danger: true,
        }
      )
      return actions
    },
  },
  methods: {
    featureName(type) {
      return this.$registry.exists('aiProviderModelFeature', type)
        ? this.$registry.get('aiProviderModelFeature', type).getName()
        : type
    },
    featureSummary(model) {
      const names = (model.feature_types || []).map(this.featureName)
      return names.length
        ? this.$t('aiProviderAdmin.availableForList', {
            features: names.join(', '),
          })
        : this.$t('aiProviderAdmin.availableForNone')
    },
    modelTestFailureLabel(model) {
      const statuses = new Set(
        (model.last_test_feature_results || []).map((result) => result.status)
      )
      return statuses.has('success') && statuses.has('failure')
        ? this.$t('aiProviderAdmin.someTestsFailed')
        : this.$t('aiProviderAdmin.testFailed')
    },
    modelTestTooltip(model) {
      const featureResults = model.last_test_feature_results || []
      if (!featureResults.length) return model.last_test_error

      return featureResults
        .map((result) => {
          const feature = this.featureName(result.feature_type)
          if (result.status === 'success') {
            return this.$t('aiProviderAdmin.featureTestPassed', { feature })
          }
          return this.$t('aiProviderAdmin.featureTestFailed', {
            feature,
            error: result.error || this.$t('aiProviderAdmin.testFailed'),
          })
        })
        .join('\n')
    },
    isModelTesting(model) {
      return this.testingModelIds.includes(model.id)
    },
    modelAnnotation(model) {
      return this.modelAnnotations[model.id] || null
    },
    isModelOverridden(model) {
      return this.modelAnnotation(model)?.muted === true
    },
    modelActionsTitle(model) {
      return (
        (this.isModelOverridden(model) &&
          this.modelAnnotation(model).tooltip) ||
        this.$t('aiProviderAdmin.moreActions')
      )
    },
    modelMenuActions(model) {
      // Testing an inherited model would spend the instance's credentials.
      if (this.provider.read_only) {
        return []
      }
      return [
        {
          key: 'test',
          label: this.$t('aiProviderAdmin.testModel'),
          icon: 'iconoir-play',
        },
        {
          key: 'edit',
          label: this.$t('action.edit'),
          icon: 'iconoir-edit',
        },
        {
          key: 'toggle',
          label: this.toggleActionTitle(model.is_enabled),
          icon: this.toggleActionIcon(model.is_enabled),
        },
        {
          key: 'delete',
          label: this.$t('action.delete'),
          icon: 'iconoir-bin',
          danger: true,
        },
      ]
    },
    onProviderAction(action) {
      const event = {
        'add-model': 'add-model',
        test: 'test-all-models',
        edit: 'edit-provider',
        toggle: 'toggle-provider',
        delete: 'delete-provider',
      }[action]
      this.$emit(event, this.provider)
    },
    onModelAction(action, model) {
      if (action === 'test') {
        this.$emit('test-model', model)
      } else if (action === 'edit') {
        this.$emit('edit-model', this.provider, model)
      } else if (action === 'toggle') {
        this.$emit('toggle-model', model)
      } else if (action === 'delete') {
        this.$emit('delete-model', model)
      }
    },
    toggleActionIcon(isEnabled) {
      return isEnabled ? 'iconoir-eye-off' : 'iconoir-eye-empty'
    },
    toggleActionTitle(isEnabled) {
      return isEnabled
        ? this.$t('aiProviderAdmin.disable')
        : this.$t('aiProviderAdmin.enable')
    },
  },
}
</script>
