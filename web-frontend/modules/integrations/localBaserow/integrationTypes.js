import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import LocalBaserowForm from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowForm'
import localBaserowIntegration from '@baserow/modules/integrations/localBaserow/assets/images/localBaserowIntegration.svg?url'

export class LocalBaserowIntegrationType extends IntegrationType {
  static getType() {
    return 'local_baserow'
  }

  get name() {
    return this.app.$i18n.t('integrationType.localBaserow')
  }

  get image() {
    return localBaserowIntegration
  }

  get iconColor() {
    return 'darker-blue'
  }

  getSummary(integration) {
    if (integration.authorized_agent) {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.localBaserowAgentSummary',
        { name: integration.authorized_agent.name }
      )
    }

    if (!integration.authorized_user) {
      return this.app.$i18n.t('localBaserowIntegrationType.localBaserowNoUser')
    }

    return this.app.$i18n.t('localBaserowIntegrationType.localBaserowSummary', {
      name: integration.authorized_user.first_name,
      username: integration.authorized_user.username,
    })
  }

  get formComponent() {
    return LocalBaserowForm
  }

  get warning() {
    return this.app.$i18n.t('localBaserowIntegrationType.localBaserowWarning')
  }

  getDefaultValues() {
    const user = this.app.$store.getters['auth/getUserObject']
    return {
      authorized_user: { username: user.username, first_name: user.first_name },
      authorized_agent: null,
      authorized_agent_id: null,
    }
  }

  getOrder() {
    return 10
  }
}
