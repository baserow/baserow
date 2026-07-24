import { defineAsyncComponent, hydrateOnIdle, markRaw } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'

const GeneralSettings = markRaw(
  defineAsyncComponent({
    loader: () =>
      import('@baserow/modules/builder/components/settings/GeneralSettings.vue'),
    hydrate: hydrateOnIdle(),
  })
)
const IntegrationSettings = markRaw(
  defineAsyncComponent({
    loader: () =>
      import('@baserow/modules/builder/components/settings/IntegrationSettings.vue'),
    hydrate: hydrateOnIdle(),
  })
)
const ThemeSettings = markRaw(
  defineAsyncComponent({
    loader: () =>
      import('@baserow/modules/builder/components/settings/ThemeSettings.vue'),
    hydrate: hydrateOnIdle(),
  })
)
const DomainsSettings = markRaw(
  defineAsyncComponent({
    loader: () =>
      import('@baserow/modules/builder/components/settings/DomainsSettings.vue'),
    hydrate: hydrateOnIdle(),
  })
)
const UserSourcesSettings = markRaw(
  defineAsyncComponent({
    loader: () =>
      import('@baserow/modules/builder/components/settings/UserSourcesSettings.vue'),
    hydrate: hydrateOnIdle(),
  })
)

export class BuilderSettingType extends Registerable {
  static getType() {
    return null
  }

  get name() {
    return null
  }

  get icon() {
    return null
  }

  get component() {
    return null
  }

  get componentPadding() {
    return true
  }

  isDeactivated({ workspace }) {
    return !!this.isDeactivatedReason({ workspace })
  }

  isDeactivatedReason({ workspace }) {
    return null
  }

  getDeactivatedModal({ workspace }) {
    return null
  }
}

export class GeneralBuilderSettingsType extends BuilderSettingType {
  static getType() {
    return 'general'
  }

  get name() {
    return this.app.$i18n.t('builderSettingTypes.generalName')
  }

  get icon() {
    return 'iconoir-settings'
  }

  getOrder() {
    return 1
  }

  get component() {
    return GeneralSettings
  }
}

export class IntegrationsBuilderSettingsType extends BuilderSettingType {
  static getType() {
    return 'integrations'
  }

  get name() {
    return this.app.$i18n.t('builderSettingTypes.integrationsName')
  }

  get icon() {
    return 'iconoir-ev-plug'
  }

  getOrder() {
    return 10
  }

  get component() {
    return IntegrationSettings
  }
}

export class ThemeBuilderSettingsType extends BuilderSettingType {
  static getType() {
    return 'theme'
  }

  get name() {
    return this.app.$i18n.t('builderSettingTypes.themeName')
  }

  get icon() {
    return 'iconoir-fill-color'
  }

  getOrder() {
    return 20
  }

  get component() {
    return ThemeSettings
  }
}

export class DomainsBuilderSettingsType extends BuilderSettingType {
  static getType() {
    return 'domains'
  }

  get name() {
    return this.app.$i18n.t('builderSettingTypes.domainsName')
  }

  get icon() {
    return 'iconoir-globe'
  }

  getOrder() {
    return 5
  }

  get component() {
    return DomainsSettings
  }
}

export class UserSourcesBuilderSettingsType extends BuilderSettingType {
  static getType() {
    return 'user_sources'
  }

  get name() {
    return this.app.$i18n.t('builderSettingTypes.userSourcesName')
  }

  get icon() {
    return 'iconoir-community'
  }

  getOrder() {
    return 15
  }

  get component() {
    return UserSourcesSettings
  }
}
