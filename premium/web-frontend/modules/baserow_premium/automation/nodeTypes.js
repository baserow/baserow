import { LocalBaserowSignalTriggerType } from '@baserow/modules/automation/nodeTypes'
import { TriggerNodeTypeMixin } from '@baserow/modules/automation/nodeTypeMixins'
import { LocalBaserowRowCommentCreatedTriggerServiceType } from '@baserow_premium/integrations/localBaserow/serviceTypes'

export class LocalBaserowRowCommentCreatedTriggerNodeType extends TriggerNodeTypeMixin(
  LocalBaserowSignalTriggerType
) {
  static getType() {
    return 'local_baserow_row_comment_created'
  }

  getOrder() {
    return 5
  }

  get labelTemplateName() {
    return 'nodeType.localBaserowRowCommentCreatedLabel'
  }

  get dataType() {
    // The comment payload is a single object, unlike the row signals.
    return 'object'
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowRowCommentCreatedTriggerServiceType.getType()
    )
  }
}
