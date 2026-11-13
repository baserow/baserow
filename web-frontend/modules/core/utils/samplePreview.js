export const SAMPLE_PREVIEW_MAX_LENGTH = 500

/**
 * Describes a sample value so it can be shown on one line next to the name of
 * the data it belongs to, for example in the data explorer.
 *
 * @param {any} value the value to describe. `undefined` means that no value is
 *  known, which is different from a known empty value.
 * @param {Number} maxLength the text of a value longer than this is cut.
 * @returns {null|{kind: string, text?: string, count?: number}} `null` when
 *  there is no value to show, otherwise one of:
 *  - `{ kind: 'empty' }` for a known value that holds nothing,
 *  - `{ kind: 'items', count }` for a list,
 *  - `{ kind: 'fields', count }` for an object,
 *  - `{ kind: 'text', text }` for everything else.
 */
export const getSamplePreview = (
  value,
  maxLength = SAMPLE_PREVIEW_MAX_LENGTH
) => {
  if (value === undefined) {
    return null
  }
  if (value === null || value === '') {
    return { kind: 'empty' }
  }
  if (Array.isArray(value)) {
    return { kind: 'items', count: value.length }
  }
  if (typeof value === 'object') {
    return { kind: 'fields', count: Object.keys(value).length }
  }
  const text = String(value).replace(/\s+/g, ' ').trim()
  if (text === '') {
    return { kind: 'empty' }
  }
  return {
    kind: 'text',
    text: text.length > maxLength ? `${text.slice(0, maxLength)}…` : text,
  }
}
