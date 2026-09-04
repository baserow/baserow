export function getTeamSubjectKey(subject) {
  return `${subject.subject_type}:${subject.subject_id}`
}

export function makeTeamSubject(subject, subjectType, secondaryLabel = null) {
  const subjectId = subjectType.getId(subject)
  const normalizedSubject = {
    ...subject,
    subject_id: subjectId,
    subject_type: subjectType.type,
  }
  if (secondaryLabel !== null) {
    normalizedSubject.email = secondaryLabel
  }
  return {
    ...normalizedSubject,
    id: getTeamSubjectKey(normalizedSubject),
  }
}
