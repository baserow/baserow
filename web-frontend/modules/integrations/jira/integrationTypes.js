import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import JiraForm from '@baserow/modules/integrations/jira/components/integrations/JiraForm'

export class JiraIntegrationType extends IntegrationType {
  static getType() {
    return 'jira'
  }

  get name() {
    return this.app.$i18n.t('integrationType.jira')
  }

  get iconClass() {
    return 'baserow-icon-jira'
  }

  get iconColor() {
    return 'muted-blue'
  }

  getSummary(integration) {
    if (!integration.url || !integration.has_api_token) {
      return this.app.$i18n.t('jiraIntegrationType.notConfigured')
    }
    return integration.url
  }

  get formComponent() {
    return JiraForm
  }

  getDefaultValues() {
    return { url: '', authentication: 'API_TOKEN', username: '' }
  }

  getOrder() {
    return 50
  }
}
