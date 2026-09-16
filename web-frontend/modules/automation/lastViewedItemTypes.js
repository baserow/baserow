import { ApplicationLastViewedItemType } from '@baserow/modules/core/lastViewedItemTypes'

export class AutomationWorkflowLastViewedItemType extends ApplicationLastViewedItemType {
  static getType() {
    return 'automation_workflow'
  }

  getOrder() {
    return 90
  }

  getApplicationTypeName() {
    return 'automation'
  }

  getName() {
    return this.app.$i18n.t('lastViewedItemType.automationWorkflow')
  }

  getRoute(entry) {
    return {
      name: 'automation-workflow',
      params: { automationId: entry.application.id, workflowId: entry.item.id },
    }
  }
}
