import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class AgentApplicationSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'agent'
    this.name = this.app.$i18n.t('agentApplication.applicationName')
    this.icon = 'iconoir-sparks'
    this.priority = 5
  }

  _getApplicationId(result) {
    const id = parseInt(result?.metadata?.application_id || result?.id)
    return isNaN(id) ? null : id
  }

  _getNavigableApplication(result) {
    const application = this.app.$store.getters['application/get'](
      this._getApplicationId(result)
    )
    if (
      application?.type !== this.type ||
      !this.app.$registry.get('application', this.type).isVisible(application)
    ) {
      return null
    }
    return application
  }

  buildUrl(result) {
    const application = this._getNavigableApplication(result)
    return application
      ? {
          name: 'agent-application',
          params: { agentId: application.id },
        }
      : null
  }

  isNavigable(result) {
    return this._getNavigableApplication(result) !== null
  }

  focusInSidebar(result, context = null) {
    return this.isNavigable(result) && super.focusInSidebar(result, context)
  }
}
