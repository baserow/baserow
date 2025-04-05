import { PaidFeature } from '@baserow_premium/paidFeatures'

export class SSOPaidFeature extends PaidFeature {
  static getType() {
    return 'sso'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'iconoir-log-in'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.sso')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class AuditLogPaidFeature extends PaidFeature {
  static getType() {
    return 'audit_log'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'baserow-icon-history'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.auditLogs')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class RBACPaidFeature extends PaidFeature {
  static getType() {
    return 'rbac'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'iconoir-community'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.rbac')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class DataSyncPaidFeature extends PaidFeature {
  static getType() {
    return 'data_sync'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'iconoir-data-transfer-down'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.dataSync')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class CoBrandingPaidFeature extends PaidFeature {
  static getType() {
    return 'co_branding'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'iconoir-media-image-list'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.coBranding')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class AdvancedWebhooksPaidFeature extends PaidFeature {
  static getType() {
    return 'advanced_webhooks'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'iconoir-web-window'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.advancedWebhooks')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}

export class SupportWebhooksPaidFeature extends PaidFeature {
  static getType() {
    return 'support'
  }

  getPlan() {
    return 'Enterprise'
  }

  getIconClass() {
    return 'iconoir-chat-bubble-question'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.support')
  }

  getImage() {
    return null
  }

  getContent() {
    return '@TODO'
  }
}
