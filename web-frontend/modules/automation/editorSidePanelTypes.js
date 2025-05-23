import { Registerable } from '@baserow/modules/core/registry'
import GeneralSidePanel from '@baserow/modules/automation/components/workflow/sidePanels/GeneralSidePanel'

export class editorSidePanelType extends Registerable {
  get label() {
    return null
  }

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

export class GeneralEditorSidePanelType extends editorSidePanelType {
  static getType() {
    return 'general'
  }

  get label() {
    return this.app.i18n.t('editorSidePanelType.general')
  }

  get component() {
    return GeneralSidePanel
  }

  getOrder() {
    return 10
  }
}
