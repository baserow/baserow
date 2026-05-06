/**
 * Checks if the provided values objects have equal matching field values. The
 * `object1IsGroup` / `object2IsGroup` flags run the corresponding side through
 * `getRowValueFromGroupValue` first. Set both to true when comparing two
 * metadata-form objects (e.g. a collapsed-state entry against a metadata
 * entry) — `isEqual` for some field types (single-select, multi-select)
 * expects row-form values.
 */
export function fieldValuesAreEqualInObjects(
  fields,
  registry,
  object1,
  object2,
  object1IsGroup = false,
  object2IsGroup = false
) {
  return fields.every((field) => {
    const fieldType = registry.get('field', field.type)
    let object1Value = object1[`field_${field.id}`]
    if (object1IsGroup) {
      object1Value = fieldType.getRowValueFromGroupValue(field, object1Value)
    }
    let object2Value = object2[`field_${field.id}`]
    if (object2IsGroup) {
      object2Value = fieldType.getRowValueFromGroupValue(field, object2Value)
    }
    return fieldType.isEqual(field, object1Value, object2Value)
  })
}
