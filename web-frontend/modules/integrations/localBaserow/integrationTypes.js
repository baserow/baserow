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
    // A trashed identity can't authenticate, so the integration isn't configured.
    if (!subject || subject.trashed) {
      return this.app.$i18n.t('localBaserowIntegrationType.localBaserowNoUser')
    }

    const subjectType = this.app.$registry.get('subject', subject.type)
    const displayName = subjectType.getDisplayName(subject)
    if (subject.user_type === 'identity') {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.localBaserowSubjectSummary',
        { type: subjectType.getTypeDisplayName(subject), name: displayName }
      )
    }

    return this.app.$i18n.t('localBaserowIntegrationType.localBaserowSummary', {
      name: displayName,
      username: subject.username,
    })
  }

  getWorkspaceHint(integration) {
    const subject = integration.authorized_subject
    // Not configured, the summary and the error message already say so.
    if (!subject || subject.trashed) {
      return null
    }

    const subjectType = this.app.$registry.get('subject', subject.type)
    const name = subjectType.getDisplayName(subject)
    if (subject.user_type === 'identity') {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.localBaserowWorkspaceSubjectHint',
        { type: subjectType.getTypeDisplayName(subject), name }
      )
    }

    return this.app.$i18n.t(
      'localBaserowIntegrationType.localBaserowWorkspaceHint',
      { name }
    )
  }

  /**
   * Mirrors what the backend does when the integration moves to the workspace: a
   * person can only authorize an integration as themselves, so one authorized as
   * someone else, or as nobody, is authorized as the user promoting it, while an
   * identity belongs to the workspace and is kept, even trashed.
   */
  getPromotionHint(integration) {
    const subject = integration.authorized_subject
    // Nobody authorized it, or the person who did no longer exists.
    if (!subject) {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.localBaserowPromotionUnauthorizedHint'
      )
    }
    // A trashed identity is kept, so it stays unusable, as its error says.
    if (subject.trashed) {
      return null
    }

    const subjectType = this.app.$registry.get('subject', subject.type)
    const name = subjectType.getDisplayName(subject)
    if (subject.user_type === 'identity') {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.localBaserowPromotionSubjectHint',
        { type: subjectType.getTypeDisplayName(subject), name }
      )
    }

    const user = this.app.$store.getters['auth/getUserObject']
    if (subject.id !== user?.id) {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.localBaserowPromotionReauthorizeHint',
        { name }
      )
    }

    return this.app.$i18n.t(
      'localBaserowIntegrationType.localBaserowPromotionHint'
    )
  }

  get formComponent() {
    return LocalBaserowForm
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

  getUpdatedValues(values, initialValues) {
    const updatedValues = super.getUpdatedValues(values, initialValues)
    const authorizationKeys = [
      'authorized_subject_id',
      'authorized_subject_type',
    ]

    if (authorizationKeys.some((key) => key in updatedValues)) {
      for (const key of authorizationKeys) {
        updatedValues[key] = values[key]
      }
    }

    return updatedValues
  }

  getErrorMessage(integration) {
    if (!integration.authorized_subject) {
      return this.app.$i18n.t('localBaserowIntegrationType.errorNoUser')
    }
    if (
      integration.authorized_subject.user_type === 'identity' &&
      integration.authorized_subject.trashed
    ) {
      return this.app.$i18n.t(
        'localBaserowIntegrationType.errorTrashedIdentity'
      )
    }
    return super.getErrorMessage(integration)
  }

  getOrder() {
    return 10
  }
}
