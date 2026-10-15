import nameAbbreviation from '@baserow/modules/core/filters/nameAbbreviation'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import { Registerable } from '@baserow/modules/core/registry'
import AgentService from '@baserow/modules/core/services/agent'

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
   * The initials shown in the avatar of the subject, or an empty string to show
   * the icon instead.
   */
  getInitials(subject) {
    return ''
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
      key: `${this.type}:${id}`,
      type: this.type,
      id,
      name: this.getDisplayName(subject),
      email: subject.email,
      subtitle: this.getSubtitle(subject) ?? this.getBadge(),
      search: this.getSearchText(subject),
      initials: this.getInitials(subject),
      icon: this.iconClass,
      color: this.avatarColor,
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

  getTypeDisplayName() {
    return this.$t('subjectType.user')
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

  getId(subject) {
    return subject.user_id ?? super.getId(subject)
  }

  getDisplayName(subject) {
    return subject.name || subject.first_name || subject.email
  }

  getInitials(subject) {
    return nameAbbreviation(this.getDisplayName(subject))
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

  fetchAssignableSubjects(workspace) {
    return Promise.resolve(workspace.users || [])
  }
}

export class AgentSubjectType extends SubjectType {
  static getType() {
    return 'core.Agent'
  }

  getOrder() {
    return 30
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

  getBadge() {
    return this.getTypeDisplayName()
  }

  isEnabled(workspace) {
    return this.app.$featureFlagIsEnabled(FF_AGENTS)
  }

  async fetchAssignableSubjects(workspace) {
    if (
      !this.app.$hasPermission('workspace.list_agents', workspace, workspace.id)
    ) {
      return []
    }
    const { data } = await AgentService(this.app.$client).list(workspace.id)
    return data.results
  }
}
