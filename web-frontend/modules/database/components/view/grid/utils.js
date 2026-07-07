import { filterVisibleFieldsFunction } from '@baserow/modules/database/utils/view'

/**
 * In the grid view, the primary field is always rendered even when its field
 * options mark it as hidden.
 */
export function filterGridViewVisibleFieldsFunction(fieldOptions) {
  const isFieldVisible = filterVisibleFieldsFunction(fieldOptions)
  return (field) => field.primary || isFieldVisible(field)
}
