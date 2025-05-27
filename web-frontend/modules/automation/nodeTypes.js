import { Registerable } from '@baserow/modules/core/registry'
import {
  ActionNodeTypeMixin,
  TriggerNodeTypeMixin,
} from '@baserow/modules/automation/nodeTypeMixins'
import LocalBaserowCreateRowActionNodeForm from '@baserow/modules/automation/components/form/node/LocalBaserowCreateRowActionNodeForm'
import LocalBaserowRowsCreatedTriggerNodeForm from '@baserow/modules/automation/components/form/node/LocalBaserowRowsCreatedTriggerNodeForm'

export class NodeType extends Registerable {
  get name() {
    return null
  }

  get description() {
    return null
  }

  get iconClass() {
    return null
  }

  get component() {
    return null
  }

  get formComponent() {
    return null
  }

  /*
  /**
   * Returns whether the node configuration is valid or not.
   * @param {object} param An object containing the workflow, node, and automation
   * @returns true if the node is in error
   */
  isInError({ workspace, workflow, node, automation }) {
    return false
  }
}

export class LocalBaserowRowsCreatedTriggerNodeType extends TriggerNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'rows_created'
  }

  get name() {
    return this.app.i18n.t('nodeType.localBaserowRowsCreated')
  }

  get description() {
    return this.app.i18n.t('nodeType.localBaserowRowsCreatedDescription')
  }

  get formComponent() {
    return LocalBaserowRowsCreatedTriggerNodeForm
  }

  getOrder() {
    return 1
  }
}

export class LocalBaserowCreateRowActionNodeType extends ActionNodeTypeMixin(
  NodeType
) {
  static getType() {
    return 'create_row'
  }

  get name() {
    return this.app.i18n.t('nodeType.localBaserowCreateRow')
  }

  get description() {
    return this.app.i18n.t('nodeType.localBaserowCreateRowDescription')
  }

  get formComponent() {
    return LocalBaserowCreateRowActionNodeForm
  }

  getOrder() {
    return 2
  }
}
