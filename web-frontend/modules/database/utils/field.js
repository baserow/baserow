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

/**
 * Extracts the default value for a field from form values based on field type.
 * @param {Object} formValues - The complete form values object
 * @param {string} fieldType - The field type (e.g., 'text', 'number', etc.)
 * @param {Object} registry - The registry object to get field type class
 * @returns {*} The default value or null if not found
 */
export function getFieldDefaultValue(formValues, fieldType, registry) {
  if (!fieldType) return null

  const fieldTypeClass = registry.get('field', fieldType)
  const defaultValueFieldName = fieldTypeClass.getDefaultValueFieldName()
  return formValues?.[defaultValueFieldName] || null
}
