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

  /**
   * Tells subjects of different types apart, for instance in the role modals
   * where users, agents and teams are listed together.
   */
  getKey(subject) {
    return `${this.getType()}:${this.getId(subject)}`
  }

  /**
   * The uid of the role the subject holds on the workspace itself, or `null`
   * when the type doesn't carry one on its records, like teams.
   */
  getWorkspaceRoleUid(subject) {
    return null
  }

  /**
   * Whether a subject of this type holds its roles itself, as users and agents
   * do. A team passes its roles on to its members instead: such a role applies
   * on the scope it is held on, but it never makes a member an admin of what is
   * inside that scope.
   */
  get holdsRolesDirectly() {
    return true
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

  getDisplayName(subject) {
    return subject.name || subject.first_name || subject.email
  }

  isCurrentUser(subject, currentUserId) {
    return this.getId(subject) === currentUserId
  }

  getWorkspaceRoleUid(subject) {
    return subject.permissions ?? null
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

  getWorkspaceRoleUid(subject) {
    return subject.role_uid ?? null
  }
}
