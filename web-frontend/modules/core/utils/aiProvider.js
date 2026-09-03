/**
 * Extract the user facing message of an AI provider API error.
 *
 * The backend spells out which model an AI feature still resolves through, so
 * that detail is preferred over the generic fallback the caller provides.
 */
export function aiProviderErrorMessage(error, fallbackMessage = '') {
  const detail = error.response?.data?.detail
  return detail?.message || detail || fallbackMessage
}
