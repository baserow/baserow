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
        :disabled="savingFeature === setting.feature_type"
        :show-search="true"
        :aria-label="
          $t('aiProviderAdmin.featureModelLabel', {
            feature: featureName(setting.feature_type),
          })
        "
        @input="updateSelection(setting, $event)"
      >
        <DropdownItem
          v-if="
            setting.state === 'invalid' &&
            (workspaceId === null ||
              (setting.mode === 'model' && workspaceId !== null))
          "
          :name="
            legacyModel
              ? $t('aiProviderAdmin.kumaInvalidFallback', {
                  model: legacyModelDisplay,
                })
              : $t('aiProviderAdmin.kumaInvalidNoFallback')
          "
          :value="setting.state"
          disabled
        />
        <DropdownItem
          v-if="workspaceId === null"
          :name="legacyModelLabel(true)"
          value="legacy"
          :disabled="!legacyModel"
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
        <DropdownItem
          v-for="option in modelOptions(setting.feature_type)"
          :key="option.id"
          :name="option.name"
          :value="`model:${option.id}`"
        />
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
    return { savingFeature: null }
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
        (setting) => this.modelOptions(setting.feature_type).length > 0
      )
    },
    legacyModel() {
      return this.$config.public.baserowEnterpriseAssistantLlmModel || ''
    },
    legacyModelDisplay() {
      return this.legacyModel || this.$t('aiProviderAdmin.kumaLegacyEmpty')
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
    providerName(provider) {
      const providerTypes = this.$store.getters['aiProvider/getTypes'](
        this.workspaceId
      )
      return (
        providerTypes.find((type) => type.type === provider.provider_type)
          ?.name || provider.provider_type
      )
    },
    modelOptions(featureType) {
      return this.providers.flatMap((provider) => {
        if (!provider.is_active) return []
        return provider.models
          .filter(
            (model) =>
              model.is_enabled &&
              (model.feature_types || []).includes(featureType)
          )
          .map((model) => ({
            id: model.id,
            name: [
              this.providerName(provider),
              model.model_identifier,
              this.workspaceId === null
                ? null
                : provider.read_only
                  ? this.$t('aiProviderAdmin.modelScopeInstance')
                  : this.$t('aiProviderAdmin.modelScopeWorkspace'),
            ]
              .filter(Boolean)
              .join(' · '),
          }))
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
    inheritedState(setting) {
      if (setting.inherited_state !== undefined) {
        return setting.inherited_state
      }
      // A rolling deployment can still be serving a backend that omits the field.
      // Infer only what the instance-wide availability flag can prove.
      return setting.feature_type === 'kuma' &&
        this.$store.getters['settings/get'].kuma?.is_enabled === false
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
      if (setting.feature_type === 'kuma') {
        return this.legacyModelLabel()
      }
      return this.$t('aiProviderAdmin.kumaNotConfigured')
    },
    legacyModelLabel(includeAction = false) {
      return this.$t(
        includeAction
          ? 'aiProviderAdmin.kumaUseLegacy'
          : 'aiProviderAdmin.kumaLegacyFallback',
        { model: this.legacyModelDisplay }
      )
    },
    inheritDisabled(setting) {
      // The backend refuses to inherit a selection this workspace cannot resolve.
      if (this.inheritedState(setting) === 'invalid') {
        return true
      }
      return (
        setting.feature_type === 'kuma' &&
        !setting.inherited_model &&
        !this.legacyModel
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
      this.savingFeature = setting.feature_type
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
        this.savingFeature = null
      }
    },
  },
}
</script>
