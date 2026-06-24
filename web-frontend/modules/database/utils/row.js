//import Vue from 'vue'
import { clone } from '@baserow/modules/core/utils/object'
import {
  getRowSortFunction,
  matchSearchFilters,
} from '@baserow/modules/database/utils/view'

/**
 * Serializes a row to make sure that the values are according to what the API expects.
 *
 * If a field doesn't have a value it will be assigned the empty value of the field
 * type.
 */
export function prepareRowForRequest(row, fields, registry) {
  return fields.reduce((preparedRow, field) => {
    const name = `field_${field.id}`
    const fieldType = registry.get('field', field.type)

    if (!fieldType.canWriteFieldValues(field)) {
      return preparedRow
    }

    preparedRow[name] = Object.prototype.hasOwnProperty.call(row, name)
      ? (preparedRow[name] = fieldType.prepareValueForUpdate(field, row[name]))
      : fieldType.getDefaultValue(field)

    return preparedRow
  }, {})
}

/**
 * This helper function prepares objects that can be used to update a row with an
 * immediate user experience.
 *
 * newRowValues: contains an object of values that can immediately be applied to the
 * row. It will hold the updated value, and the related field values we can can
 * update optimisticly.
 *
 * oldRowValues: contains an object with the same keys as the newRowValues, but with
 * their old values. This can be used to revert back to the old values if something
 * fails.
 *
 * updateRequestValues: contains the values that new values prepared for an API
 * request update. These are the ones you want to pass into the service.
 */
export function prepareNewOldAndUpdateRequestValues(
  row,
  allFields,
  field,
  value,
  oldValue,
  registry
) {
  const newRowValues = {
    id: row.id,
    [`field_${field.id}`]: value,
  }
  const oldRowValues = {
    id: row.id,
    [`field_${field.id}`]: oldValue,
  }
  const updateRequestValues = { id: row.id }

  // Loop over all fields except the one that we're going to update, to figure out
  // if the `onRowChange` return value of the field has changed. If so, we want to
  // add that to immediately add that to the `newRowValues` immediately, so that the
  // update feels instant to the user.
  allFields
    .filter((f) => f.id !== field.id)
    .forEach((fieldToCall) => {
      const fieldType = registry.get('field', fieldToCall.type)
      const fieldID = `field_${fieldToCall.id}`
      const currentFieldValue = row[fieldID]
      const optimisticFieldValue = fieldType.onRowChange(
        row,
        fieldToCall,
        currentFieldValue
      )

      if (currentFieldValue !== optimisticFieldValue) {
        newRowValues[fieldID] = optimisticFieldValue
        oldRowValues[fieldID] = currentFieldValue
      }
    })

  const fieldType = registry.get('field', field.type)
  const updateValue = fieldType.prepareValueForUpdate(field, value)
  updateRequestValues[`field_${field.id}`] = updateValue

  return { newRowValues, oldRowValues, updateRequestValues }
}

/**
 * Multi-field variant of `prepareNewOldAndUpdateRequestValues`. Given a single
 * row and multiple `(field, value, oldValue)` triples, return one combined
 * `{newRowValues, oldRowValues, updateRequestValues}` so the row can be patched
 * once with every field change at the same time. Side-effect optimistic values
 * (`onRowChange`) are still computed for unedited fields against a virtual row
 * that already reflects every new value.
 */
export function prepareRowMultiFieldUpdate(
  row,
  allFields,
  fieldValuePairs,
  registry
) {
  const newRowValues = { id: row.id }
  const oldRowValues = { id: row.id }
  const updateRequestValues = { id: row.id }
  const editedFieldIds = new Set(fieldValuePairs.map((p) => p.field.id))

  for (const { field, value, oldValue } of fieldValuePairs) {
    const fieldKey = `field_${field.id}`
    newRowValues[fieldKey] = value
    oldRowValues[fieldKey] = oldValue
    const fieldType = registry.get('field', field.type)
    updateRequestValues[fieldKey] = fieldType.prepareValueForUpdate(
      field,
      value
    )
  }

  const virtualRow = { ...row, ...newRowValues }
  for (const otherField of allFields) {
    if (editedFieldIds.has(otherField.id)) {
      continue
    }
    const fieldType = registry.get('field', otherField.type)
    const fieldKey = `field_${otherField.id}`
    const currentFieldValue = row[fieldKey]
    const optimisticFieldValue = fieldType.onRowChange(
      virtualRow,
      otherField,
      currentFieldValue
    )
    if (currentFieldValue !== optimisticFieldValue) {
      newRowValues[fieldKey] = optimisticFieldValue
      oldRowValues[fieldKey] = currentFieldValue
    }
  }

  return { newRowValues, oldRowValues, updateRequestValues }
}

/**
 * Compute the row-form values a brand-new row should start with,
 * combining: explicit caller-supplied values (highest priority),
 * view-level default_row_values, and each field type's own default
 * (`getNewRowValue`). Returns a `{ field_X: rowFormValue, ... }` map
 * suitable for an optimistic insert; pass each value through the
 * field type's `prepareValueForUpdate` separately to build the BE
 * payload.
 *
 * This is the same computation the flat-grid create flow previously did
 * inline; extracting it keeps row default handling reusable by other grid
 * code without duplicating the defaults logic.
 */
export function buildNewRowDefaults({
  view,
  fields,
  registry,
  suppliedValues = {},
}) {
  const defaultItems = view?.default_row_values ?? []
  const defaultsByFieldId = {}
  for (const item of defaultItems) {
    if (item.enabled && (item.value != null || item.function)) {
      defaultsByFieldId[item.field] = item
    }
  }
  const newRow = {}
  for (const field of fields) {
    const name = `field_${field.id}`
    if (name in suppliedValues) {
      newRow[name] = suppliedValues[name]
      continue
    }
    const fieldTypeKey = field._?.type?.type || field.type
    const fieldType = registry.get('field', fieldTypeKey)
    const defaultViewItem = defaultsByFieldId[field.id]
    const supportedFunctions = fieldType.getSupportedDefaultValueFunctions
      ? fieldType.getSupportedDefaultValueFunctions().map((f) => f.name)
      : []
    if (
      defaultViewItem?.function &&
      supportedFunctions.includes(defaultViewItem.function)
    ) {
      newRow[name] = fieldType.resolveDefaultValueFunction(
        defaultViewItem.function,
        field
      )
    } else if (
      defaultViewItem?.value != null &&
      (!defaultViewItem.field_type ||
        defaultViewItem.field_type === fieldTypeKey)
    ) {
      newRow[name] = fieldType.parseDefaultRowValue(
        field,
        defaultViewItem.value
      )
    } else if (fieldType.getNewRowValue) {
      newRow[name] = fieldType.getNewRowValue(field)
    }
  }
  return newRow
}

/**
 * Decide whether a row still belongs at its current position after a change:
 * whether it still matches the view's filters, and whether it lands at the same
 * sorted index amongst the comparison set. The grouped grid can pass only the
 * rows from the current group section; the flat grid can pass every loaded row.
 */
export function computeRowMatchFlags({
  row,
  view,
  fields,
  registry,
  rowsInSortingGroup = [],
  groupBys = [],
}) {
  const matchFilters = view?.filters_disabled
    ? true
    : matchSearchFilters(
        registry,
        view.filter_type,
        view.filters ?? [],
        view.filter_groups ?? [],
        fields ?? [],
        row
      )

  let matchSortings = true
  if (fields && fields.length > 0) {
    const sortFn = getRowSortFunction(
      registry,
      view?.sortings ?? [],
      fields,
      groupBys
    )
    const currentIndex = rowsInSortingGroup.findIndex((r) => r.id === row.id)
    if (currentIndex >= 0) {
      const rowsForSorting = [...rowsInSortingGroup]
      rowsForSorting[currentIndex] = {
        ...rowsForSorting[currentIndex],
        ...row,
      }
      const sorted = rowsForSorting.sort(sortFn)
      const sortedIndex = sorted.findIndex((r) => r.id === row.id)
      matchSortings = currentIndex === sortedIndex
    }
  }

  return { matchFilters, matchSortings }
}

/**
 * Compute the per-cell flags used by the area / checkbox multi-cell
 * highlight: `{selected, top, right, bottom, left}`. The view's row
 * component passes this object to `GridViewCell` which uses it to
 * paint the outer borders only on the rectangle's perimeter (not on
 * internal cell edges).
 *
 * Pure function. Grid row components can call it with their own coordinate
 * model as long as coordinates use the same model as the flat grid's
 * multi-select state: integer row index in the visible row list and integer
 * field index in the visible fields list.
 */
export function computeMultiSelectPosition({
  isAreaSelectionActive,
  isCheckboxSelected,
  rowIndex,
  fieldIndex,
  rowIndexRange,
  fieldIndexRange,
}) {
  const position = {
    selected: false,
    top: false,
    right: false,
    bottom: false,
    left: false,
  }
  if (!isAreaSelectionActive) {
    if (isCheckboxSelected) position.selected = true
    return position
  }
  const [minRow, maxRow] = rowIndexRange ?? [-1, -1]
  const [minField, maxField] = fieldIndexRange ?? [-1, -1]
  if (
    rowIndex < 0 ||
    fieldIndex < 0 ||
    rowIndex < minRow ||
    rowIndex > maxRow ||
    fieldIndex < minField ||
    fieldIndex > maxField
  ) {
    return position
  }
  position.selected = true
  if (rowIndex === minRow) position.top = true
  if (rowIndex === maxRow) position.bottom = true
  if (fieldIndex === minField) position.left = true
  if (fieldIndex === maxField) position.right = true
  return position
}

/**
 * Returns an object only containing the read-only values of the row, and the id.
 * This can be used to update a row with the return data after making an update
 * request. The reason we need to do this, is because the other values might have
 * changed in the meantime, and they should not be updated.
 */
export function extractRowReadOnlyValues(row, allFields, registry) {
  const readOnlyValues = { id: row.id }
  allFields.forEach((field) => {
    const fieldType = registry.get('field', field.type)
    const fieldKey = `field_${field.id}`
    if (
      fieldType.isReadOnlyField(field) &&
      Object.prototype.hasOwnProperty.call(row, fieldKey)
    ) {
      readOnlyValues[fieldKey] = row[fieldKey]
    }
  })
  return readOnlyValues
}

export function extractChangedFields(
  row,
  allFields,
  updatedFieldIds,
  registry
) {
  const rowValues = { id: row.id }
  allFields.forEach((field) => {
    const fieldType = registry.get('field', field.type)
    const fieldKey = `field_${field.id}`
    if (
      (fieldType.isReadOnlyField(field) &&
        Object.prototype.hasOwnProperty.call(row, fieldKey)) ||
      updatedFieldIds.includes(field.id)
    ) {
      rowValues[fieldKey] = row[fieldKey]
    }
  })
  return rowValues
}

/**
 * Call the given updateFunction with the current value of the row metadata type and
 * set the new value. If the row metadata type does not exist yet, it will be
 * created.
 */
export function updateRowMetadataType(row, rowMetadataType, updateFunction) {
  const currentValue = row._.metadata[rowMetadataType]
  const newValue = updateFunction(currentValue)

  if (!Object.prototype.hasOwnProperty.call(row._.metadata, rowMetadataType)) {
    const metaDataCopy = clone(row._.metadata)
    metaDataCopy[rowMetadataType] = newValue
    row._['metadata'] = metaDataCopy
  } else {
    row._.metadata[rowMetadataType] = newValue
  }
}

/**
 * Return the metadata of a row. If the metadata does not exist yet, it will be created
 * as an empty object.
 */
export function getRowMetadata(row, metadata = {}) {
  return { ...metadata, ...(row.metadata || {}) }
}

/**
 * Compute where `row` belongs among `existingRows` according to the given sorts.
 *
 * Returns `{ anchorRowId, sortedIndex, isFirst, isLast }`:
 * - `anchorRowId` is the id of the row immediately before `row` in sorted order,
 *   or null when `row` sorts first.
 * - `sortedIndex` is the 0-based position of `row` in the merged, sorted result.
 *
 * Expressing the insert position by row identity rather than numeric index lets
 * both flat-array stores and group-tree stores consume the result without
 * needing to agree on a shared index space.
 */
export function computeRowInsertPosition(
  row,
  existingRows,
  sorts,
  fields,
  registry,
  groupBys = []
) {
  const sortFn = getRowSortFunction(registry, sorts, fields, groupBys)
  const sorted = [...existingRows, row].sort(sortFn)
  const sortedIndex = sorted.findIndex((r) => r.id === row.id)
  const anchorRowId = sortedIndex > 0 ? sorted[sortedIndex - 1].id : null
  return {
    anchorRowId,
    sortedIndex,
    isFirst: sortedIndex === 0,
    isLast: sortedIndex === sorted.length - 1,
  }
}
