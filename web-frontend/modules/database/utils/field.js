/**
 * Find the primary field in a list of fields.
 * If no primary field is found, return the first field.
 * @param fields
 * @returns {*}
 */
export function getPrimaryOrFirstField(fields) {
  const primaryField = fields.find((field) => field.primary)
  return primaryField || fields[0]
}

/**
 * Checks if a given field has at least one compatible filterType
 * @param field
 * @param filterTypes
 * @returns {boolean}
 */
export function hasCompatibleFilterTypes(field, filterTypes) {
  for (const type in filterTypes) {
    if (filterTypes[type].fieldIsCompatible(field)) {
      return true
    }
  }
  return false
}

/**
 * Unique key used in combination with the `SelectRowModal`.
 */
export function getPersistentFieldOptionsKey(fieldId) {
  return `link-row-${fieldId}`
}
