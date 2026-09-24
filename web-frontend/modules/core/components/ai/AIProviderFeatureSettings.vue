<template>
  <section v-if="settings.length" class="ai-provider-feature-settings">
    <div class="ai-provider-feature-settings__heading">
      <div>
        <h2 class="ai-provider-feature-settings__title">
          {{ $t('aiProviderAdmin.featureSettingsTitle') }}
        </h2>
        <p class="ai-provider-feature-settings__description">
          {{ $t('aiProviderAdmin.featureSettingsDescription') }}
        </p>
      </div>
    </div>
    <div
      v-for="setting in settings"
      :key="setting.feature_type"
      class="ai-provider-feature-settings__row"
    >
      <div class="ai-provider-feature-settings__feature">
        <strong>{{ featureName(setting.feature_type) }}</strong>
        <span>{{ featureDescription(setting.feature_type) }}</span>
      </div>
      <Dropdown
        :value="selection(setting)"
        :disabled="savingFeatures.includes(setting.feature_type)"
        :show-search="true"
        :aria-label="
          $t('aiProviderAdmin.featureModelLabel', {
            feature: featureName(setting.feature_type),
          })
        "
        @input="updateSelection(setting, $event)"
      >
        <template #selectedValue>
          <span class="dropdown__selected-text" :title="selectedLabel(setting)">
            {{ selectedLabel(setting) }}
          </span>
        </template>
        <DropdownItem
          v-if="
            setting.state === 'invalid' &&
            (workspaceId === null ||
              (setting.mode === 'model' && workspaceId !== null))
          "
          :name="
            legacyModel(setting)
              ? $t('aiProviderAdmin.kumaInvalidFallback', {
                  model: legacyModelDisplay(setting),
                })
              : $t('aiProviderAdmin.kumaInvalidNoFallback')
          "
          :value="setting.state"
          disabled
        />
        <DropdownItem
          v-if="workspaceId === null && supportsLegacyModel(setting)"
          :name="legacyModelLabel(setting, true)"
          value="legacy"
          :disabled="!legacyModel(setting)"
        />
        <DropdownItem
          v-if="workspaceId !== null"
          :name="inheritLabel(setting)"
          value="inherit"
          :disabled="inheritDisabled(setting)"
        />
        <DropdownItem
          :name="
            workspaceId === null
              ? $t('aiProviderAdmin.kumaDisabled')
              : $t('aiProviderAdmin.kumaDisabledInWorkspace')
          "
          value="disabled"
        />
        <DropdownSection
          v-for="group in modelGroups(setting.feature_type)"
          :key="group.id"
          :title="group.name"
        >
          <DropdownItem
            v-for="option in group.models"
            :key="option.id"
            :name="`${group.name} · ${option.name}`"
            :value="`model:${option.id}`"
            :indented="true"
          >
            <span class="select__item-name-text" :title="option.name">
              {{ option.name }}
            </span>
          </DropdownItem>
        </DropdownSection>
      </Dropdown>
    </div>
    <p v-if="!hasEligibleModels" class="ai-provider-feature-settings__hint">
      {{ $t('aiProviderAdmin.noFeatureModels') }}
    </p>
  </section>
</template>

<script>
export default {
  name: 'AIProviderFeatureSettings',
  props: {
    workspaceId: { type: Number, default: null },
  },
  data() {
    return { savingFeatures: [] }
  },
  computed: {
    settings() {
      return this.$store.getters['aiProvider/getFeatureSettings'](
        this.workspaceId
      )
    },
    providers() {
      return this.$store.getters['aiProvider/getAll'](this.workspaceId)
    },
    hasEligibleModels() {
      return this.settings.some(
        (setting) => this.modelGroups(setting.feature_type).length > 0
      )
    },
  },
  methods: {
    feature(type) {
      return this.$registry.exists('aiProviderModelFeature', type)
        ? this.$registry.get('aiProviderModelFeature', type)
        : null
    },
    featureName(type) {
      return this.feature(type)?.getName() || type
    },
    featureDescription(type) {
      return this.feature(type)?.getDescription() || ''
    },
    supportsLegacyModel(setting) {
      return this.feature(setting.feature_type)?.supportsLegacyModel() || false
    },
    legacyModel(setting) {
      return this.feature(setting.feature_type)?.getLegacyModel() || ''
    },
    legacyModelDisplay(setting) {
      return (
        this.legacyModel(setting) || this.$t('aiProviderAdmin.kumaLegacyEmpty')
      )
    },
    providerName(provider) {
      const providerTypes = this.$store.getters['aiProvider/getTypes'](
        this.workspaceId
      )
      return (
        providerTypes.find((type) => type.type === provider.provider_type)
          ?.name || provider.provider_type
      )
    },
    providerLabel(provider) {
      const scope =
        this.workspaceId === null
          ? null
          : provider.read_only
            ? this.$t('aiProviderAdmin.modelScopeInstance')
            : this.$t('aiProviderAdmin.modelScopeWorkspace')
      return [this.providerName(provider), scope].filter(Boolean).join(' · ')
    },
    modelGroups(featureType) {
      return this.providers.flatMap((provider) => {
        if (!provider.is_active) return []
        const models = provider.models
          .filter(
            (model) =>
              model.is_enabled &&
              (model.feature_types || []).includes(featureType)
          )
          .map((model) => ({ id: model.id, name: model.model_identifier }))
        if (models.length === 0) return []
        return [{ id: provider.id, name: this.providerLabel(provider), models }]
      })
    },
    selection(setting) {
      if (setting.mode === 'model' && setting.model) {
        return `model:${setting.model.id}`
      }
      if (setting.state === 'invalid' && setting.mode === 'model') {
        return 'invalid'
      }
      if (this.workspaceId === null && setting.state === 'unconfigured') {
        // Also handles a rolling deployment where an older backend still
        // reports the historical `disabled` mode for an absent instance row.
        return 'legacy'
      }
      return setting.mode
    },
    selectedLabel(setting) {
      const selection = this.selection(setting)
      if (selection.startsWith('model:')) {
        const modelId = Number(selection.slice(6))
        for (const group of this.modelGroups(setting.feature_type)) {
          const model = group.models.find(
            (candidate) => candidate.id === modelId
          )
          if (model) {
            return `${group.name} · ${model.name}`
          }
        }
        return setting.model?.model_identifier || ''
      }
      if (selection === 'invalid') {
        return this.legacyModel(setting)
          ? this.$t('aiProviderAdmin.kumaInvalidFallback', {
              model: this.legacyModelDisplay(setting),
            })
          : this.$t('aiProviderAdmin.kumaInvalidNoFallback')
      }
      if (selection === 'legacy') {
        return this.legacyModelLabel(setting, true)
      }
      if (selection === 'inherit') {
        return this.inheritLabel(setting)
      }
      return this.workspaceId === null
        ? this.$t('aiProviderAdmin.kumaDisabled')
        : this.$t('aiProviderAdmin.kumaDisabledInWorkspace')
    },
    inheritedState(setting) {
      if (setting.inherited_state !== undefined) {
        return setting.inherited_state
      }
      // A rolling deployment can still be serving a backend that omits the field.
      // Infer only what the instance-wide availability flag can prove.
      return this.$store.getters['settings/get'][setting.feature_type]
        ?.is_enabled === false
        ? 'disabled'
        : 'unconfigured'
    },
    inheritedModelLabel(setting) {
      if (setting.inherited_model) {
        const provider = this.providers.find(
          (candidate) =>
            candidate.provider_type === setting.inherited_model.provider_type
        )
        const providerName = provider
          ? this.providerName(provider)
          : setting.inherited_model.provider_type
        return `${providerName} · ${setting.inherited_model.model_identifier}`
      }
      const inheritedState = this.inheritedState(setting)
      if (inheritedState === 'disabled') {
        return this.$t('aiProviderAdmin.kumaDisabled')
      }
      if (inheritedState === 'invalid') {
        return this.$t('aiProviderAdmin.kumaInheritedUnavailable')
      }
      if (this.supportsLegacyModel(setting)) {
        return this.legacyModelLabel(setting)
      }
      return this.$t('aiProviderAdmin.kumaNotConfigured')
    },
    legacyModelLabel(setting, includeAction = false) {
      return this.$t(
        includeAction
          ? 'aiProviderAdmin.kumaUseLegacy'
          : 'aiProviderAdmin.kumaLegacyFallback',
        { model: this.legacyModelDisplay(setting) }
      )
    },
    inheritDisabled(setting) {
      // The backend refuses to inherit a selection this workspace cannot resolve.
      const inheritedState = this.inheritedState(setting)
      if (inheritedState === 'invalid') {
        return true
      }
      return (
        inheritedState === 'unconfigured' &&
        this.supportsLegacyModel(setting) &&
        !setting.inherited_model &&
        !this.legacyModel(setting)
      )
    },
    inheritLabel(setting) {
      return this.$t('aiProviderAdmin.kumaUseInstance', {
        model: this.inheritedModelLabel(setting),
      })
    },
    async updateSelection(setting, selection) {
      if (!selection || selection === this.selection(setting)) return
      const values = selection.startsWith('model:')
        ? { mode: 'model', model_id: Number(selection.slice(6)) }
        : { mode: selection }
      this.savingFeatures.push(setting.feature_type)
      try {
        await this.$store.dispatch('aiProvider/updateFeatureSetting', {
          featureType: setting.feature_type,
          values,
          workspaceId: this.workspaceId,
        })
      } catch {
        this.$store.dispatch('toast/error', {
          title: this.$t('aiProviderAdmin.featureSettingError'),
          message: this.$t('aiProviderAdmin.featureSettingErrorDescription'),
        })
      } finally {
        this.savingFeatures = this.savingFeatures.filter(
          (featureType) => featureType !== setting.feature_type
        )
      }
    },
  },
}
</script>
