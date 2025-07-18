import { TwoWaySyncStrategyType } from '@baserow/modules/database/twoWaySyncStrategyTypes'

export class RealtimePushTwoWaySyncStrategyType extends TwoWaySyncStrategyType {
  static getType() {
    return 'realtime_push'
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('enterpriseTwoWaySyncStrategyType.realtimePushDescription')
  }
}
