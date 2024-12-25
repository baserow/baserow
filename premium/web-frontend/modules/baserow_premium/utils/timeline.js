/**
 * Returns the fields that can represent a date.
 */
export const filterDateFields = ($registry, fields) => {
  return fields.filter((f) =>
    $registry.get('field', f.type).canRepresentDate(f)
  )
}

/**
 * Returns the field matching the provided fieldId if it can represent a date field.
 */
export const getDateField = ($registry, fields, fieldId) => {
  const field = fields.find((field) => field.id === fieldId)
  if (field) {
    const fieldType = $registry.get('field', field.type)
    if (fieldType.canRepresentDate(field)) {
      return field
    }
  }
  return null
}

/**
 * Returns true if the provided date fields are valid and compatible.
 */
export const dateSettinsAreValid = (startDateField, endDateField) => {
  if (!startDateField || !endDateField) {
    return false
  }

  return dateFieldsAreCompatible(startDateField, endDateField)
}

/**
 * Returns true if the provided date fields are compatible and can be used together
 * in a timeline view.
 */
export const dateFieldsAreCompatible = (startDateField, endDateField) => {
  const startHasTime = startDateField.date_include_time
  const startTz = startDateField.date_force_timezone
  const endHasTime = endDateField.date_include_time
  const endTz = endDateField.date_force_timezone
  return (
    Object.prototype.hasOwnProperty.call(startDateField, 'date_include_time') &&
    Object.prototype.hasOwnProperty.call(endDateField, 'date_include_time') &&
    startHasTime === endHasTime &&
    // we need to check the timezone only if the time is included
    ((startHasTime && startTz === endTz) || !startHasTime)
  )
}

/**
 * Returns the date value of a row field, parsed by the field type and the field
 * options.
 */
export const getRowDateValue = ($registry, row, field) => {
  if (!row) {
    return null
  }

  const fieldType = $registry.get('field', field.type)
  const value = row[`field_${field.id}`]
  if (!value) {
    return null
  }

  return fieldType.parseInputValue(field, value)
}
