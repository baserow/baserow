import { SubjectType } from '@baserow/modules/core/subjectTypes'
import TeamService from '@baserow_enterprise/services/team'

export class TeamSubjectType extends SubjectType {
  static getType() {
    return 'baserow_enterprise.Team'
  }

  getOrder() {
    return 20
  }

  get avatarColor() {
    return 'neutral'
  }

  get iconClass() {
    return 'iconoir-community'
  }

  getTypeDisplayName() {
    return this.$t('subjectType.team')
  }

  getPluralTypeDisplayName() {
    return this.$t('subjectType.teams')
  }

  getSubtitle(subject) {
    return this.$t('subjectType.teamMembers', { count: subject.subject_count })
  }

  getBadge() {
    return this.getTypeDisplayName()
  }

  async fetchAssignableSubjects(workspace) {
    const { data } = await TeamService(this.app.$client).fetchAll(workspace.id)
    return data
  }
}
