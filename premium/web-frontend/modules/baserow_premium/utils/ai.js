/**
 * Get the AI field generation status for a specific field on a row.
 * Centralizes the row → metadata → ai_field → fieldId → status traversal
 * so callers don't repeat fragile optional-chaining paths.
 *
 * @param {object} row - The row object (must have `._` populated)
 * @param {number|string} fieldId - The AI field ID
 * @returns {string|null} The status string (e.g. 'generating', 'error') or null
 */
export function getAIFieldStatus(row, fieldId) {
  const aiField = row._ && row._.metadata && row._.metadata.ai_field
  const fieldMetadata = aiField && aiField[fieldId]
  return (fieldMetadata && fieldMetadata.status) || null
}
