import { Registerable } from '@baserow/modules/core/registry'
import {
  ActionNodeTypeMixin,
  TriggerNodeTypeMixin,
} from '@baserow/modules/automation/nodeTypeMixins'
import {
  LocalBaserowCreateRowWorkflowServiceType,
  LocalBaserowRowsCreatedTriggerServiceType,
} from '@baserow/modules/integrations/localBaserow/serviceTypes'

export class NodeType extends Registerable {
  get name() {
    return this.serviceType.name
  }

  get description() {
    return this.serviceType.description
  }

  get serviceType() {
    throw new Error('This method must be implemented')
  }

  get iconClass() {
    return null
  }

  get component() {
    return null
  }

  get formComponent() {
    return this.serviceType.formComponent
  }

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
