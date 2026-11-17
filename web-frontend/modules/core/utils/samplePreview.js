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

// The values the backend `sanitize_sample_data` puts in place of the real
// ones when sample data is exported without sensitive data.
const PLACEHOLDER_STRING = 'Example'
const PLACEHOLDER_NUMBER = 0
const PLACEHOLDER_BOOLEAN = false

/**
 * Whether the given data of a sample holds placeholders only, which is what
 * is left of the sample data of an imported workspace or template: it keeps
 * the shape of the result, but none of its values. Such a sample has nothing
 * worth showing as an example.
 *
 * Data without any value at all (empty or `null`s only) doesn't count: there
 * is no placeholder in it to recognise.
 *
 * @param {any} data the `data` of a service's sample data.
 * @returns {Boolean} true when every value is a placeholder.
 */
export const isPlaceholderSampleData = (data) => {
  let placeholders = 0
  const onlyPlaceholders = (value) => {
    if (value === null || value === undefined) {
      return true
    }
    if (Array.isArray(value)) {
      return value.every(onlyPlaceholders)
    }
    if (typeof value === 'object') {
      return Object.values(value).every(onlyPlaceholders)
    }
    placeholders += 1
    return (
      value === PLACEHOLDER_STRING ||
      value === PLACEHOLDER_NUMBER ||
      value === PLACEHOLDER_BOOLEAN
    )
  }
  return onlyPlaceholders(data) && placeholders > 0
}
