import { AdminType } from '@baserow/modules/core/adminTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import {
  AuditLogPaidFeature,
  DataScannerPaidFeature,
  SSOPaidFeature,
} from '@baserow_enterprise/paidFeatures'

class EnterpriseAdminType extends AdminType {
  getDeactivatedModal() {
    return [PaidFeaturesModal, {}]
  }
}

export class AuthProvidersType extends EnterpriseAdminType {
  static getType() {
    return 'auth-providers'
  }

  getIconClass() {
    return 'iconoir-log-in'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('adminType.Authentication')
  }

  getRouteName() {
    return 'admin-auth-providers'
  }

  getOrder() {
    return 100
  }

  isDeactivated() {
    return !this.app.$hasFeature(EnterpriseFeatures.SSO)
  }

  getDeactivatedModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': SSOPaidFeature.getType() },
    ]
  }
}

export class AuditLogType extends EnterpriseAdminType {
  static getType() {
    return 'audit-log'
  }

  getIconClass() {
    return 'baserow-icon-history'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('adminType.AuditLog')
  }

  getRouteName() {
    return 'admin-audit-log'
  }

  getOrder() {
    return 110
  }

  isDeactivated() {
    return !this.app.$hasFeature(EnterpriseFeatures.AUDIT_LOG)
  }

  getDeactivatedModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': AuditLogPaidFeature.getType() },
    ]
  }
}

export class DataScannerType extends EnterpriseAdminType {
  static getType() {
    return 'data-scanner'
  }

  getIconClass() {
    return 'iconoir-search'
  }

  getName() {
    const { $i18n } = this.app
    return $i18n.t('adminType.DataScanner')
  }

  getRouteName() {
    return 'admin-data-scanner'
  }

  getOrder() {
    return 120
  }

  isDeactivated() {
    return !this.app.$hasFeature(EnterpriseFeatures.DATA_SCANNER)
  }

  getDeactivatedModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': DataScannerPaidFeature.getType() },
    ]
  }
}
