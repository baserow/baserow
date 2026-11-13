import Avatar from '@baserow/modules/core/components/Avatar'
import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'
import { Registerable } from '@baserow/modules/core/registry'
import SubjectService from '@baserow/modules/core/services/subject'
import { FF_IDENTITIES } from '@baserow/modules/core/plugins/featureFlags'

export class SubjectType extends Registerable {
  /** Component owning this subject type's avatar color, icon and shape. */
  get avatarComponent() {
    return (this._avatarComponent ??= ({ subject, size }) => (
      <Avatar
        initials={nameAbbreviation(this.getDisplayName(subject) || '')}
        color="blue"
        rounded
        size={size}
      />
    ))
  }

  get iconClass() {
    return null
  }

  getId(subject) {
    return subject.id
  }

  /**
   * Tells subjects of different types apart, for instance in the share dialog
   * where users, identities and teams are listed together.
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
   * Whether a subject of this type holds its roles itself, as users and identities
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

  /**
   * The name of the tab that lists the subjects of this type in the invite
   * input.
   */
  getTabDisplayName() {
    return this.getPluralTypeDisplayName()
  }

  getDisplayName(subject) {
    return subject.name
  }

  /**
   * The second line shown below the name of the subject, if any.
   */
  getSubtitle(subject) {
    return null
  }

  /**
   * The badge shown next to the name of the subject, if any.
   */
  getBadge() {
    return null
  }

  /**
   * The text the invite input matches a search against.
   */
  getSearchText(subject) {
    return this.getDisplayName(subject)
  }

  isCurrentUser() {
    return false
  }

  isUser() {
    return false
  }

  /**
   * Whether subjects of this type can be searched and given a role, for
   * example because a feature flag is on.
   */
  isEnabled(workspace) {
    return true
  }

  /**
   * Fetches the subjects of the workspace that can be given a role.
   */
  fetchAssignableSubjects(workspace) {
    return Promise.resolve([])
  }

  /**
   * The subject as an option of the invite input.
   */
  getInviteOption(subject) {
    const id = this.getId(subject)
    return {
      key: this.getKey(subject),
      type: this.type,
      id,
      name: this.getDisplayName(subject),
      email: subject.email,
      subtitle: this.getSubtitle(subject) ?? this.getBadge(subject),
      search: this.getSearchText(subject),
      avatarComponent: this.avatarComponent,
      subject,
    }
  }
}

export class UserSubjectType extends SubjectType {
  static getType() {
    return 'auth.User'
  }

  getOrder() {
    return 10
  }

  get avatarComponent() {
    return (this._avatarComponent ??= ({ subject, size }) => {
      const isIdentity = subject.user_type === 'identity'
      return (
        <Avatar
          class={isIdentity ? 'identity-avatar' : undefined}
          initials={
            isIdentity
              ? ''
              : nameAbbreviation(this.getDisplayName(subject) || '')
          }
          icon={isIdentity ? this.identityIconClass : ''}
          color={isIdentity ? 'purple' : 'blue'}
          rounded={!isIdentity}
          size={size}
        />
      )
    })
  }

  getTypeDisplayName(subject) {
    return this.$t(
      subject?.user_type === 'identity'
        ? 'subjectType.identity'
        : 'subjectType.user'
    )
  }

  getBadge(subject) {
    return subject?.user_type === 'identity'
      ? this.$t('subjectType.identity')
      : null
  }

  getPluralTypeDisplayName() {
    return this.$t('subjectType.users')
  }

  getTabDisplayName() {
    return this.$t('subjectType.members')
  }

  get iconClass() {
    return 'iconoir-user'
  }

  get identityIconClass() {
    return 'iconoir-lock'
  }

  getId(subject) {
    return subject.subject_id ?? subject.user_id ?? super.getId(subject)
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

  getSubtitle(subject) {
    return subject.email ?? null
  }

  getSearchText(subject) {
    return `${this.getDisplayName(subject)} ${subject.email ?? ''}`.trim()
  }

  isCurrentUser(subject, currentUserId) {
    return this.getId(subject) === currentUserId
  }

  async fetchAssignableSubjects(workspace) {
    const users = workspace.users || []
    if (
      !this.app.$featureFlagIsEnabled?.(FF_IDENTITIES) ||
      !this.app.$hasPermission(
        'workspace.list_identities',
        workspace,
        workspace.id
      )
    ) {
      return users
    }
    const identities = await SubjectService(this.app.$client).listAll(
      workspace.id,
      {
        userType: 'identity',
      }
    )
    return [...users, ...identities]
  }

  isUser() {
    return true
  }

  getWorkspaceRoleUid(subject) {
    return subject.permissions ?? subject.role_uid ?? null
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

  // Anonymous visitors are display-only and cannot receive role assignments.
  isEnabled(workspace) {
    return false
  }
}
