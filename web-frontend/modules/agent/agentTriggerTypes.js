import { Registerable } from '@baserow/modules/core/registry'
import { textThenTriggerData } from '@baserow/modules/agent/utils/triggers'

/**
 * Changes how an Agent hosts a trigger service type, under the service type's
 * name. One is written only where an Agent needs something else than the
 * service type gives; every other trigger service type is hosted as it is.
 */
export class AgentTriggerType extends Registerable {
  /**
   * @returns {string[]} The fields of the service type's form an Agent doesn't
   *   offer.
   */
  get hiddenFormFields() {
    return []
  }

  /**
   * @returns {object|null} The opening message formula of a new trigger, or
   *   null for the one every trigger type can have.
   */
  getDefaultMessage() {
    return null
  }
}

export class HTTPAgentTriggerType extends AgentTriggerType {
  static getType() {
    return 'http_trigger'
  }

  get hiddenFormFields() {
    return ['test_url', 'wait_for_response', 'response_timeout_seconds']
  }

  getDefaultMessage() {
    return textThenTriggerData(
      this.app.$i18n.t('agent.httpTriggerDefaultMessage'),
      'raw_body'
    )
  }
}
