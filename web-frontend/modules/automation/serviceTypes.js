import { Registerable } from '@baserow/modules/core/registry'
import PeriodicTriggerServiceForm from '@baserow/modules/automation/components/services/PeriodicTriggerServiceForm'

export class PeriodicTriggerServiceType extends Registerable {
  static getType() {
    return 'periodic_trigger'
  }

  get name() {
    return this.app.i18n.t('serviceType.periodicTrigger')
  }

  get description() {
    return this.app.i18n.t('serviceType.periodicTriggerDescription')
  }

  get formComponent() {
    return PeriodicTriggerServiceForm
  }

  getDataSchema() {
    return {
      type: 'object',
      title: this.app.i18n.t('serviceType.periodicTrigger'),
      properties: {
        triggered_at: {
          type: 'string',
          title: this.app.i18n.t('serviceType.periodicTriggerTriggeredAt'),
        },
      },
    }
  }

  isInError() {
    return false
  }
}
