import { defineAsyncComponent, hydrateOnIdle } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'

const NodeSidePanel = defineAsyncComponent({
  loader: () =>
    import('@baserow/modules/automation/components/workflow/sidePanels/NodeSidePanel'),
  hydrate: hydrateOnIdle(),
})
const HistorySidePanel = defineAsyncComponent({
  loader: () =>
    import('@baserow/modules/automation/components/workflow/sidePanels/HistorySidePanel'),
  hydrate: hydrateOnIdle(),
})

export class editorSidePanelType extends Registerable {
  get component() {
    return null
  }

  get guidedTourAttr() {
    return ''
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

  get guidedTourAttr() {
    return 'automation-node-sidepanel'
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

  get guidedTourAttr() {
    return 'automation-history-sidepanel'
  }

  get component() {
    return HistorySidePanel
  }

  getOrder() {
    return 20
  }
}
