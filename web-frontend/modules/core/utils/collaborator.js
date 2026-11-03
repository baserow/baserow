import {
  SubjectType,
  UserSubjectType,
} from '@baserow/modules/core/subjectTypes'

const userSubjectType = new UserSubjectType()
const fallbackSubjectType = new SubjectType()

/** Resolve a typed value while retaining compatibility with legacy User values. */
export function getCollaboratorSubjectType(value, registry) {
  const type = value?.type ?? UserSubjectType.getType()
  if (registry?.exists('subject', type)) {
    return registry.get('subject', type)
  }
  return type === UserSubjectType.getType()
    ? userSubjectType
    : fallbackSubjectType
}

/** Resolve display names without interpreting non-human Subject IDs as User IDs. */
export function getCollaboratorName(collaboratorValue, store, registry) {
  if (
    !collaboratorValue ||
    typeof collaboratorValue !== 'object' ||
    (!collaboratorValue.id && !collaboratorValue.name)
  ) {
    return ''
  }
  const subjectType = getCollaboratorSubjectType(collaboratorValue, registry)
  return subjectType.getDisplayName(collaboratorValue, {
    resolveUserName: (value) => {
      if (store.getters['workspace/getAll'].length === 0) return value.name
      return (
        store.getters['workspace/getUserById'](value.id)?.name ?? value.name
      )
    },
  })
}
