import SubjectRoleAssignmentRows from '@baserow_enterprise/components/member-roles/SubjectRoleAssignmentRows'

/**
 * The expansion of a members, teams or agents table row into the roles the
 * subject holds on databases, tables and views, toggled by a "+N" chip in the
 * column of the subject's workspace role.
 *
 * @param {string} subjectType The subject type of the rows, like `auth.User`.
 * @param {string} columnKey The key of the column of the workspace role.
 * @param {Function} getSubjectId Returns the subject's id of a row.
 * @param {Function} isReadOnly Returns whether the roles of a row can't be changed.
 */
export function getSubjectRoleAssignmentsRowExpansion({
  subjectType,
  columnKey,
  getSubjectId = (row) => row.id,
  isReadOnly = () => false,
}) {
  return {
    component: SubjectRoleAssignmentRows,
    columnKey,
    isExpandable: (row) => row.role_assignment_count > 0,
    getToggleLabel: (row) => `+${row.role_assignment_count}`,
    getProps: (row) => ({
      subjectType,
      subjectId: getSubjectId(row),
      roleColumnKey: columnKey,
      readOnly: isReadOnly(row),
    }),
  }
}
