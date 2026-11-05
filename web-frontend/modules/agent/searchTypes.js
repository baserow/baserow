import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'
import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class AgentApplicationSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
    this.type = AGENT_APPLICATION_TYPE
    this.name = this.app.$i18n.t('applicationType.agent')
    this.icon = 'baserow-icon-agent'
    this.priority = 5
  }

  _getApplicationId(result) {
    const id = parseInt(result?.metadata?.application_id || result?.id)
    return isNaN(id) ? null : id
  }

  buildUrl(result) {
    const agentId = this._getApplicationId(result)
    if (!agentId) {
      return null
    }
    return { name: 'agent-application', params: { agentId } }
  }

  isNavigable(result) {
    return this._getApplicationId(result) !== null
  }
}
