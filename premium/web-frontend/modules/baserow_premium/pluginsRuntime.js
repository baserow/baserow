import { BaserowPlugin } from '@baserow/modules/core/plugins'

/** License checks required by published pages without loading application UI. */
export class PremiumRuntimePlugin extends BaserowPlugin {
  static getType() {
    return 'premium'
  }

  hasFeature(feature, forSpecificWorkspace) {
    return this.app.$licenseHandler.hasFeature(feature, forSpecificWorkspace)
  }
}
