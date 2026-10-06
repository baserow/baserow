import {
  isObject,
  formatValue,
  rowsTable,
} from '@baserow_enterprise/utils/agentTriggerPreview'

/**
 * Previews the arguments of a tool call that stored no preview of its own:
 * the first list of objects (rows to write, items to send) becomes a table
 * and every other argument a label/value row, so the raw JSON is never the
 * only way to review a step.
 */
export function buildApprovalPreview(args) {
  if (!isObject(args)) {
    return null
  }
  const fields = []
  let table = null
  for (const [key, value] of Object.entries(args)) {
    const rows =
      table === null &&
      Array.isArray(value) &&
      value.length > 0 &&
      value.every(isObject)
        ? rowsTable(value)
        : null
    if (rows) {
      table = rows
    } else {
      const formatted = formatValue(value)
      if (formatted !== '') {
        fields.push({ key, value: formatted })
      }
    }
  }
  if (fields.length === 0 && table === null) {
    return null
  }
  return { kind: 'args', fields, table }
}
