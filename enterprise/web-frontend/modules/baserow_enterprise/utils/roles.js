/**
 * Filters the role array by scope_type and subject_type.
 *
 * @param {Array} roles The role array to filter
 * @param {object} filter An object that can contains a `scopeType` or a `subjectType`
 *    property which is used to filter the role list.
 * @returns a filtered list of roles
 */
export const filterRoles = (roles, { scopeType, subjectType }) => {
  return roles.filter(
    ({ allowedScopeTypes, allowedSubjectTypes, isVisible }) =>
      isVisible &&
      (scopeType === undefined ||
        !Array.isArray(allowedScopeTypes) ||
        allowedScopeTypes.includes(scopeType)) &&
      (subjectType === undefined ||
        !Array.isArray(allowedSubjectTypes) ||
        allowedSubjectTypes.includes(subjectType))
  )
}
