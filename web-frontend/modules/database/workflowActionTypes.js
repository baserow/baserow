import { WorkflowActionType } from '@baserow/modules/core/workflowActionTypes'
import DatabaseWorkflowActionWithService from '@baserow/modules/database/components/field/DatabaseWorkflowActionWithService'
import {
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowUpdateRowWorkflowServiceType,
  LocalBaserowDeleteRowWorkflowServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'

/**
 * Base for a database workflow action backed by a service.
 *
 * Unlike the builder's equivalent it has no `execute`: a button click
 * dispatches the whole sequence server side, so nothing runs in the browser.
 * The type only supplies what the editor needs to render the action.
 */
export class DatabaseWorkflowActionServiceType extends WorkflowActionType {
  get form() {
    return DatabaseWorkflowActionWithService
  }

  get label() {
    return this.serviceType.name
  }

  get icon() {
    return this.serviceType.icon
  }

  get serviceType() {
    throw new Error('Must be set on the type.')
  }
}

export class CreateRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'create_row'
  }

  getOrder() {
    return 10
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowWorkflowServiceType.getType()
    )
  }
}

export class UpdateRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'update_row'
  }

  getOrder() {
    return 20
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowUpdateRowWorkflowServiceType.getType()
    )
  }
}

export class DeleteRowWorkflowActionType extends DatabaseWorkflowActionServiceType {
  static getType() {
    return 'delete_row'
  }

  getOrder() {
    return 30
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowDeleteRowWorkflowServiceType.getType()
    )
  }
}
