import { Registerable } from '@baserow/modules/core/registry'
import PremiumFeaturesObject from '@baserow_premium/features'

/**
 *
 */
export class LicenseType extends Registerable {
  /**
   * A human readable name of the license type.
   */
  getName() {
    return null
  }

  /**
   * The css class that should be applied when rendering the badge of a license of
   * this type.
   */
  getLicenseBadgeColor() {
    throw new Error('Must be set by the implementing sub class.')
  }

  /**
   * A list of features that this license provides.
   */
  getFeatures() {
    throw new Error('Must be set by the implementing sub class.')
  }

  getFeaturesDescription() {
    return this.getName() + ' Features'
  }

  showInTopSidebarWhenActive() {
    throw new Error('Must be set by the implementing sub class.')
  }

  getTopSidebarTooltip() {
    throw new Error('Must be set by the implementing sub class.')
  }

  getOrder() {
    throw new Error('Must be set by the implementing sub class.')
  }

  getSeatsManuallyAssigned() {
    throw new Error('Must be set by the implementing sub class.')
  }

  getLicenseDescription(license) {
    throw new Error('Must be set by the implementing sub class.')
  }

  getLicenseSeatOverflowWarning(license) {
    throw new Error('Must be set by the implementing sub class.')
  }
}

export class PremiumLicenseType extends LicenseType {
  static getType() {
    return 'premium'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('licenses.premium')
  }

  getLicenseBadgeColor() {
    return 'cyan'
  }

  getFeatures() {
    return [PremiumFeaturesObject.PREMIUM]
  }

  getFeaturesDescription() {
    const { i18n } = this.app
    return [
      {
        name: i18n.t('license.premiumFeatureName'),
        enabled: true,
      },
      {
        name: i18n.t('license.enterpriseFeatureName'),
        enabled: false,
      },
      {
        name: i18n.t('license.supportFeatureName'),
        enabled: false,
      },
    ]
  }

  getTopSidebarTooltip() {
    const { i18n } = this.app
    return i18n.t('premiumTopSidebar.premium')
  }

  showInTopSidebarWhenActive() {
    return true
  }

  getOrder() {
    return 10
  }

  getSeatsManuallyAssigned() {
    return true
  }

  getLicenseDescription(license) {
    const { i18n } = this.app
    return i18n.t('license.description', license)
  }

  getLicenseSeatOverflowWarning(license) {
    return ''
  }
}

