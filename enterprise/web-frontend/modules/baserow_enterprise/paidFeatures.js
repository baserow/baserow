import { PaidFeature } from '@baserow_premium/paidFeatures'

export class SSOPaidFeature extends PaidFeature {
  static getType() {
    return 'sso'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-log-in'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.sso')
  }

  getImage() {
    return '/img/features/sso.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.ssoContent')
  }
}

export class AuditLogPaidFeature extends PaidFeature {
  static getType() {
    return 'audit_log'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'baserow-icon-history'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.auditLogs')
  }

  getImage() {
    return '/img/features/audit_logs.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.auditLogsContent')
  }
}

export class RBACPaidFeature extends PaidFeature {
  static getType() {
    return 'rbac'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-community'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.rbac')
  }

  getImage() {
    return '/img/features/role_based_access_control.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.rbacContent')
  }
}

export class DataSyncPaidFeature extends PaidFeature {
  static getType() {
    return 'data_sync'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-data-transfer-down'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.dataSync')
  }

  getImage() {
    return '/img/features/data_sync.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.dataSyncContent')
  }
}

export class AdvancedWebhooksPaidFeature extends PaidFeature {
  static getType() {
    return 'advanced_webhooks'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-web-window'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.advancedWebhooks')
  }

  getImage() {
    return '/img/features/advanced_webhooks.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.advancedWebhooksContent')
  }
}

export class FieldLevelPermissionsPaidFeature extends PaidFeature {
  static getType() {
    return 'field_level_permissions'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-lock'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.fieldLevelPermissions')
  }

  getImage() {
    return '/img/features/field_level_permissions.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.fieldLevelPermissionsContent')
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
    return '/img/features/co_branding.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.coBrandingContent')
  }
}

export class SupportPaidFeature extends PaidFeature {
  static getType() {
    return 'support'
  }

  getPlan() {
    return 'Advanced'
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
    return this.app.i18n.t('enterpriseFeatures.supportContent')
  }
}

export class BuilderBrandingPaidFeature extends PaidFeature {
  static getType() {
    return 'builder_branding'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-eye-close'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.builderBranding')
  }

  getImage() {
    return null
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.builderBrandingContent')
  }
}

export class BuilderFileInputElementPaidFeature extends PaidFeature {
  static getType() {
    return 'builder_file_input'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-attachment'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.builderFileInputElement')
  }

  getImage() {
    return null
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.builderFileInputElementContent')
  }
}

export class BuilderCustomCodePaidFeature extends PaidFeature {
  static getType() {
    return 'builder_custom_code'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'iconoir-code-brackets'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.builderCustomCode')
  }

  getImage() {
    return null
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.builderCustomCodeContent')
  }
}

export class DateDependencyPaidFeature extends PaidFeature {
  static getType() {
    return 'date_dependency'
  }

  getPlan() {
    return 'Advanced'
  }

  getIconClass() {
    return 'baserow-icon-dependency'
  }

  getName() {
    return this.app.i18n.t('enterpriseFeatures.dateDependency')
  }

  getImage() {
    return '/img/features/date_dependency.png'
  }

  getContent() {
    return this.app.i18n.t('enterpriseFeatures.dateDependencyContent')
  }
}
