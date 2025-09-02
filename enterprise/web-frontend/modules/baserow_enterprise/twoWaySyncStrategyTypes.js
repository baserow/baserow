import { TwoWaySyncStrategyType } from '@baserow/modules/database/twoWaySyncStrategyTypes'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal.vue'
import { DataSyncPaidFeature } from '@baserow_enterprise/paidFeatures'
import EnterpriseFeatures from '@baserow_enterprise/features'

export class RealtimePushTwoWaySyncStrategyType extends TwoWaySyncStrategyType {
  static getType() {
    return 'realtime_push'
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('enterpriseTwoWaySyncStrategyType.realtimePushDescription')
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.DATA_SYNC, workspaceId)
  }

  getDeactivatedClickModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': DataSyncPaidFeature.getType() },
    ]
  }
}
