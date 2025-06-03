import { Registerable } from '@baserow/modules/core/registry'
import {
  ActionNodeTypeMixin,
  TriggerNodeTypeMixin,
} from '@baserow/modules/automation/nodeTypeMixins'
import {
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowRowsCreatedTriggerServiceType,
  LocalBaserowRowsDeletedTriggerServiceType,
  LocalBaserowRowsUpdatedTriggerServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'
import localBaserowIntegration from '@baserow/modules/integrations/localBaserow/assets/images/localBaserowIntegration.svg'

export class NodeType extends Registerable {
  /**
   * The display name of the node type.
   * The name is derived from the service type's name.
   * @returns {string} - The display name for the node.
   */
  get name() {
    return this.serviceType.name
  }

  /**
   * The node type's description.
   * The description is derived from the service type's description.
   * @returns {string} - The node's description.
   */
  get description() {
    return this.serviceType.description
  }

  /**
   * New nodes must implement this method to return their
   * specific service type.
   * @throws {Error} If the method is not implemented.
   */
  get serviceType() {
    throw new Error('This method must be implemented')
  }

  /**
   * The node type's image, which will be displayed in dropdowns.
   * @returns - The node's image.
   */
  get image() {
    return localBaserowIntegration
  }

  /**
   * The node type's editor component. Not yet implemented.
   * @returns {object|null} - The node's editor component.
   */
  get component() {
    return null
  }

  /**
   * The node type's form component.
   * The component is derived from the service type's form component.
   * @returns {object} - The node's form component.
   */
  get formComponent() {
    return this.serviceType.formComponent
  }

  /**
   * Returns whether the node is in-error or not.
   * By default, this is derived from the service type's `isInError`
   * method, but can be overridden by the node type.
   * @returns {boolean} - Whether the properties are in-error.
   */
  isInError({ node, automation }) {
    return this.serviceType.isInError({ service: node.service })
  }
}

export class LocalBaserowRowsCreatedTriggerNodeType extends TriggerNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'rows_created'
  }

  getOrder() {
    return 1
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowRowsCreatedTriggerServiceType.getType()
    )
  }
}

export class LocalBaserowRowsUpdatedTriggerNodeType extends TriggerNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'rows_updated'
  }

  getOrder() {
    return 2
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowRowsUpdatedTriggerServiceType.getType()
    )
  }
}

export class LocalBaserowRowsDeletedTriggerNodeType extends TriggerNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'rows_deleted'
  }

  getOrder() {
    return 3
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowRowsDeletedTriggerServiceType.getType()
    )
  }
}

export class LocalBaserowCreateRowActionNodeType extends ActionNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'create_row'
  }

  getOrder() {
    return 2
  }

  get serviceType() {
    return this.app.$registry.get(
      'service',
      LocalBaserowCreateRowWorkflowServiceType.getType()
    )
  }
}
