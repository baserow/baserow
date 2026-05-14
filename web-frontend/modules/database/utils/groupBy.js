/**
 * Checks if the provided values objects have equal matching field values. If can
 * optionally run the value of the first object through the
 * `getRowValueFromGroupValue` method.
 */
export function fieldValuesAreEqualInObjects(
  fields,
  registry,
  object1,
  object2,
  object1IsGroup = false
) {
  return fields.every((field) => {
    const fieldType = registry.get('field', field.type)
    let object1Value = object1[`field_${field.id}`]
    if (object1IsGroup) {
      object1Value = fieldType.getRowValueFromGroupValue(field, object1Value)
    }
    const object2Value = object2[`field_${field.id}`]
    return fieldType.isEqual(field, object1Value, object2Value)
  })
}
