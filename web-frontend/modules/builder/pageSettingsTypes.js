import { Registerable } from '@baserow/modules/core/registry'
import PageSettings from '@baserow/modules/builder/components/page/settings/PageSettings'
import PageVisibilitySettings from '@baserow/modules/builder/components/page/settings/PageVisibilitySettings'

export class PageSettingType extends Registerable {
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

  getOrder() {
    return this.order
  }
}

export class PagePageSettingsType extends PageSettingType {
  static getType() {
    return 'page'
  }

  get name() {
    return this.app.i18n.t('pageSettingsTypes.pageName')
  }

  get icon() {
    return 'iconoir-settings'
  }

  get component() {
    return PageSettings
  }

  getOrder() {
    return 10
  }
}

export class PageVisibilitySettingsType extends PageSettingType {
  static getType() {
    return 'page_visibility'
  }

  get name() {
    return this.app.i18n.t('pageVisibilitySettingsTypes.pageName')
  }

  get icon() {
    return 'iconoir-eye-empty'
  }

  get component() {
    return PageVisibilitySettings
  }

  getOrder() {
    return 20
  }
}
