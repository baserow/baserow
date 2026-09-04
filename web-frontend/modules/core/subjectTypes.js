import { Registerable } from '@baserow/modules/core/registry'

export class SubjectType extends Registerable {
  get avatarColor() {
    return 'blue'
  }

  get iconClass() {
    return null
  }

  getId(subject) {
    return subject.id
  }

  getTypeDisplayName() {
    return this.type
  }

  getPluralTypeDisplayName() {
    return this.getTypeDisplayName()
  }

  getDisplayName(subject) {
    return subject.name
  }

  isCurrentUser() {
    return false
  }
}

export class UserSubjectType extends SubjectType {
  static getType() {
    return 'auth.User'
  }

  getTypeDisplayName() {
    return this.$t('subjectType.user')
  }

  getPluralTypeDisplayName() {
    return this.$t('subjectType.users')
  }

  get iconClass() {
    return 'iconoir-user'
  }

  getId(subject) {
    return subject.user_id ?? super.getId(subject)
  }

  getDisplayName(
    subject,
    { currentUserId, currentUserName, resolveUserName } = {}
  ) {
    if (currentUserName && subject.id === currentUserId) {
      return currentUserName
    }
    return resolveUserName
      ? resolveUserName(subject)
      : subject.name || subject.first_name || subject.email
  }

  isCurrentUser(subject, currentUserId) {
    return this.getId(subject) === currentUserId
  }
}

export class AnonymousUserSubjectType extends SubjectType {
  static getType() {
    return 'anonymous'
  }

  getTypeDisplayName() {
    return this.$t('subjectType.anonymousUser')
  }

  getDisplayName(subject, { anonymousName } = {}) {
    return anonymousName || super.getDisplayName(subject)
  }
}

export class AgentSubjectType extends SubjectType {
  static getType() {
    return 'core.Agent'
  }

  get avatarColor() {
    return 'purple'
  }

  get iconClass() {
    return 'baserow-icon-agent'
  }

  getTypeDisplayName() {
    return this.$t('subjectType.agent')
  }

  getPluralTypeDisplayName() {
    return this.$t('subjectType.agents')
  }
}
