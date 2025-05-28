import { Registerable } from '@baserow/modules/core/registry'
import NodeSidePanel from '@baserow/modules/automation/components/workflow/sidePanels/NodeSidePanel.vue'
import HistorySidePanel from '@baserow/modules/automation/components/workflow/sidePanels/HistorySidePanel.vue'

export class editorSidePanelType extends Registerable {
  get component() {
    return null
  }

  isDeactivated() {
    return false
  }

  getOrder() {
    return this.order
  }
}

export class NodeEditorSidePanelType extends editorSidePanelType {
  static getType() {
    return 'node'
  }

  get component() {
    return NodeSidePanel
  }

  getOrder() {
    return 10
  }
}

export class HistoryEditorSidePanelType extends editorSidePanelType {
  static getType() {
    return 'history'
  }

  get component() {
    return HistorySidePanel
  }

  getOrder() {
    return 20
  }
}
