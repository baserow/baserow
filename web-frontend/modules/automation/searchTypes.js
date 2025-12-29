import { ApplicationSearchType } from '@baserow/modules/core/search/types/base'

export class AutomationSearchType extends ApplicationSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'automation'
    this.name = 'Automation'
    this.icon = 'baserow-icon-automation'
    this.priority = 4
  }

  _getApplicationId(result) {
    const id = parseInt(result?.metadata?.application_id || result?.id)
    return isNaN(id) ? null : id
  }

  _getApplicationChildren(application) {
    return application.workflows
  }

  _getApplicationPath(application, children) {
    return {
      name: 'automation-workflow',
      params: { automationId: application.id, workflowId: children[0].id },
    }
  }
}
