export function getTeamSubjectKey(subject) {
  return `${subject.subject_type}:${subject.subject_id}`
}
