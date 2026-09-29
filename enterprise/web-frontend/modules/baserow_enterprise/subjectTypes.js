import { SubjectType } from '@baserow/modules/core/subjectTypes'

export class TeamSubjectType extends SubjectType {
  static getType() {
    return 'baserow_enterprise.Team'
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
}
