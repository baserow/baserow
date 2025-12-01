import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class AutomationSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'automation'
    this.name = 'Automation'
    this.icon = 'baserow-icon-automation'
    this.priority = 4
  }

  buildUrl(result, context = null) {
    const appId = result?.metadata?.application_id || result?.id
    if (!appId) {
      return null
    }

    if (context && context.store) {
      const automation = context.store.getters['application/get'](appId)
      if (
        automation &&
        automation.workflows &&
        automation.workflows.length > 0
      ) {
        const workflows = [...automation.workflows].sort(
          (a, b) => a.order - b.order
        )
        if (workflows.length > 0) {
          return `/automation/${appId}/workflow/${workflows[0].id}`
        }
      }
    }

    return null
  }
}
