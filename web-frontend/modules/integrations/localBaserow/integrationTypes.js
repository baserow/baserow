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
    const subject = integration.authorized_subject
    // A trashed agent can't authenticate, so the integration isn't configured.
    if (!subject || subject.trashed) {
      return this.app.$i18n.t('localBaserowIntegrationType.localBaserowNoUser')
    }

    const subjectType = this.app.$registry.get('subject', subject.type)
    const displayName = subjectType.getDisplayName(subject)
    if (!subjectType.isUser()) {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.localBaserowSubjectSummary',
        { type: subjectType.getTypeDisplayName(), name: displayName }
      )
    }

    return this.app.$i18n.t('localBaserowIntegrationType.localBaserowSummary', {
      name: displayName,
      username: subject.username,
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
      authorized_subject: {
        id: user.id,
        type: 'auth.User',
        username: user.username,
        first_name: user.first_name,
      },
      authorized_subject_id: user.id,
      authorized_subject_type: 'auth.User',
    }
  }

  getErrorMessage(integration) {
    if (
      integration.authorized_subject?.type === 'core.Agent' &&
      integration.authorized_subject.trashed
    ) {
      return this.app.$i18n.t('localBaserowIntegrationType.errorTrashedAgent')
    }
    return super.getErrorMessage(integration)
  }

  getOrder() {
    return 10
  }
}
