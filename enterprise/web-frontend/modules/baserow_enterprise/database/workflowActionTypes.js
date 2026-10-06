import { DatabaseWorkflowActionServiceType } from '@baserow/modules/database/workflowActionTypes'
import { CoreRunAgentServiceType } from '@baserow_enterprise/integrations/core/serviceTypes'

/**
 * A button that starts an agent conversation for the clicked row. The result
 * carries the conversation link, so an "Open URL" action after it can take
 * the person straight to the chat.
 */
export class CoreRunAgentWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'run_agent'
  }

  getOrder() {
    return 75
  }

  get serviceType() {
    return this.app.$registry.get('service', CoreRunAgentServiceType.getType())
  }

  getDataSchema(applicationContext, workflowAction) {
    return this.serviceType.getDataSchema(
      applicationContext,
      workflowAction.service
    )
  }
}
