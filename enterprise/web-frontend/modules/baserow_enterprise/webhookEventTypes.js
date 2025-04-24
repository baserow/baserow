import {
  WebhookEventType,
  viewExample,
} from '@baserow/modules/database/webhookEventTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { AdvancedWebhooksPaidFeature } from '@baserow_enterprise/paidFeatures'

class EnterpriseWebhookEventType extends WebhookEventType {
  getDeactivatedText() {
    return this.app.i18n.t('enterprise.deactivated')
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': AdvancedWebhooksPaidFeature.getType() },
    ]
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(
      EnterpriseFeatures.ADVANCED_WEBHOOKS,
      workspaceId
    )
  }

  getFeatureName() {
    return this.app.i18n.t('enterpriseFeatures.advancedWebhooks')
  }
}

export class RowsEnterViewWebhookEventType extends EnterpriseWebhookEventType {
  static getType() {
    return 'view.rows_entered'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('webhook.rowsEnterVieweventType')
  }

  getExamplePayload(database, table, rowExample) {
    const payload = super.getExamplePayload(database, table, rowExample)
    payload.view = viewExample
    payload.fields = Object.keys(rowExample)
    payload.rows = [rowExample]
    payload.total_count = 1
    return payload
  }

  getHasRelatedView() {
    return true
  }

  getRelatedViewPlaceholder() {
    const { i18n } = this.app
    return i18n.t('webhookForm.triggerWhenRowsEnterView')
  }

  getRelatedViewHelpText() {
    const { i18n } = this.app
    return i18n.t('webhookForm.helpTriggerWhenRowsEnterView')
  }
}
