import { AgentTriggerType } from '@baserow/modules/agent/agentTriggerTypes'
import { sentenceWithTriggerData } from '@baserow/modules/agent/utils/triggers'
import { LocalBaserowRowCommentPostedTriggerServiceType } from '@baserow_enterprise/integrations/localBaserow/serviceTypes'

export class RowCommentPostedAgentTriggerType extends AgentTriggerType {
  static getType() {
    return LocalBaserowRowCommentPostedTriggerServiceType.getType()
  }

  getFormProps({ runAsName }) {
    return { mentionName: runAsName }
  }

  getDefaultMessage() {
    return sentenceWithTriggerData(
      this.app.$i18n.t('rowCommentTrigger.message', {
        author: '{user_name}',
        row: '{row_id}',
        table: '{table_id}',
        text: '{text}',
      })
    )
  }
}
