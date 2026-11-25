import { Registerable } from '@baserow/modules/core/registry'
import {
  sentenceWithTriggerData,
  textThenTriggerData,
} from '@baserow/modules/agent/utils/triggers'

const ROWS_MESSAGE_VALUES = Object.freeze({
  count: '{count}',
  table: '{table}',
  rows: '{rows}',
})

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
   * @param {object} context What the Agent offers its service form.
   * @param {string} context.runAsName The name of the identity the Agent acts
   *   as, or '' when it has none it can act as.
   * @returns {object} The props the service form takes from the Agent.
   */
  getFormProps({ runAsName }) {
    return {}
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

export class InboundEmailAgentTriggerType extends AgentTriggerType {
  static getType() {
    return 'email_trigger'
  }

  // An Agent has no draft that a test address could start a test run of.
  get hiddenFormFields() {
    return ['test_email_address']
  }

  getDefaultMessage() {
    return sentenceWithTriggerData(
      this.app.$i18n.t('agent.emailTriggerDefaultMessage', {
        sender: '{from.address}',
        subject: '{subject}',
        body: '{body_text}',
      })
    )
  }
}

/**
 * Opens a new row trigger with how many rows changed in which table, then the
 * rows.
 */
class RowsAgentTriggerType extends AgentTriggerType {
  /**
   * @returns {string} The i18n key of the sentence, whose `{count}`, `{table}`
   *   and `{rows}` are values of the trigger's data.
   */
  get defaultMessageKey() {
    throw new Error('Must be set on the row trigger type.')
  }

  getDefaultMessage() {
    return sentenceWithTriggerData(
      this.app.$i18n.t(this.defaultMessageKey, ROWS_MESSAGE_VALUES)
    )
  }
}

export class RowsCreatedAgentTriggerType extends RowsAgentTriggerType {
  static getType() {
    return 'local_baserow_rows_created'
  }

  get defaultMessageKey() {
    return 'agent.rowsCreatedDefaultMessage'
  }
}

export class RowsUpdatedAgentTriggerType extends RowsAgentTriggerType {
  static getType() {
    return 'local_baserow_rows_updated'
  }

  get defaultMessageKey() {
    return 'agent.rowsUpdatedDefaultMessage'
  }
}

export class RowsDeletedAgentTriggerType extends RowsAgentTriggerType {
  static getType() {
    return 'local_baserow_rows_deleted'
  }

  get defaultMessageKey() {
    return 'agent.rowsDeletedDefaultMessage'
  }
}
