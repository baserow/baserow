import { TriggerServiceTypeMixin } from '@baserow/modules/core/serviceTypes'
import { LocalBaserowTableServiceType } from '@baserow/modules/integrations/localBaserow/serviceTypes'
import LocalBaserowSignalTriggerServiceForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowSignalTriggerServiceForm.vue'

export class LocalBaserowRowCommentCreatedTriggerServiceType extends TriggerServiceTypeMixin(
  LocalBaserowTableServiceType
) {
  static getType() {
    return 'local_baserow_row_comment_created'
  }

  get name() {
    return this.app.$i18n.t('serviceType.localBaserowRowCommentCreated')
  }

  get description() {
    return this.app.$i18n.t(
      'serviceType.localBaserowRowCommentCreatedDescription'
    )
  }

  get icon() {
    return 'iconoir-chat-bubble'
  }

  get formComponent() {
    return LocalBaserowSignalTriggerServiceForm
  }

  getErrorMessage({ service }) {
    if (service !== undefined && !service.table_id) {
      return this.app.$i18n.t('serviceType.errorNoTableSelected')
    }
    return super.getErrorMessage({ service })
  }
}
