import EnterpriseFeaturesObject from '@baserow_enterprise/features'
import PremiumFeaturesObject from '@baserow_premium/features'
import { LicenseType } from '@baserow_premium/licenseTypes'
import EnterpriseFeatures from '@baserow_enterprise/components/EnterpriseFeatures'

export class EnterpriseWithoutSupportLicenseType extends LicenseType {
  static getType() {
    return 'enterprise_without_support'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('enterprise.license')
  }

  getLicenseBadgeColor() {
    return 'neutral'
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
        enabled: true,
      },
      {
        name: i18n.t('license.supportFeatureName'),
        enabled: false,
      },
    ]
  }

  getFeatures() {
    return [
      PremiumFeaturesObject.PREMIUM,
      EnterpriseFeaturesObject.RBAC,
      EnterpriseFeaturesObject.SSO,
      EnterpriseFeaturesObject.TEAMS,
      EnterpriseFeaturesObject.AUDIT_LOG,
      EnterpriseFeaturesObject.ENTERPRISE_SETTINGS,
      EnterpriseFeaturesObject.DATA_SYNC,
    ]
  }

  getTopSidebarTooltip() {
    const { i18n } = this.app
    return i18n.t('enterprise.sidebarTooltip')
  }

  showInTopSidebarWhenActive() {
    return true
  }

  getOrder() {
    return 100
  }

  getSeatsManuallyAssigned() {
    return false
  }

  getLicenseDescription(license) {
    const { i18n } = this.app
    return i18n.t('enterprise.licenseDescription')
  }

  getLicenseSeatOverflowWarning(license) {
    const { i18n } = this.app
    return i18n.t('enterprise.overflowWarning')
  }

  getFeaturesComponent() {
    return EnterpriseFeatures
  }
}

export class EnterpriseLicenseType extends EnterpriseWithoutSupportLicenseType {
  static getType() {
    return 'enterprise'
  }

  getFeatures() {
    return super.getFeatures().concat(EnterpriseFeaturesObject.SUPPORT)
  }

  getFeaturesDescription() {
    const description = super.getFeaturesDescription()
    description[2].enabled = true
    return description
  }

  getFeaturesComponent() {
    return null
  }
}
