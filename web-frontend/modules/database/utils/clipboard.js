/**
 * Copies the given text to the clipboard by temporarily creating a textarea and
 * using the documents `copy` command.
 * @param {string} text
 */
export const copyToClipboard = (text) => {
  navigator.clipboard.writeText(text)
}

export const LOCAL_STORAGE_CLIPBOARD_KEY = 'baserow.clipboardData'

/**
 * Returns the rich clipboard data stored for the exact plain-text clipboard value.
 * The browser clipboard cannot contain Baserow's field metadata, so grid copies keep
 * that metadata in local storage and use the plain text as an integrity check.
 *
 * @param {string} textRawData The current plain-text clipboard value.
 * @returns {Array|null} The matching two-dimensional rich clipboard data.
 */
export const getStoredRichClipboardData = (textRawData) => {
  try {
    const clipboardData = JSON.parse(
      localStorage.getItem(LOCAL_STORAGE_CLIPBOARD_KEY)
    )
    const clipboardDataTextToCompare = clipboardData.text.replaceAll(
      '\r\n',
      '\n'
    )
    const textRawDataToCompare = textRawData.replaceAll('\r\n', '\n')
    if (clipboardDataTextToCompare === textRawDataToCompare) {
      return clipboardData.json
    }
  } catch (e) {
    // Invalid or inaccessible local storage is equivalent to no rich clipboard data.
  }

  try {
    localStorage.removeItem(LOCAL_STORAGE_CLIPBOARD_KEY)
  } catch (e) {
    // There is nothing else to clear when local storage itself is inaccessible.
  }
  return null
}

/**
 * Returns Markdown when the clipboard contains one rich-text grid cell. This is used
 * by database-hosted rich-text editors, which otherwise only see the quoted TSV text.
 *
 * @param {string} textRawData The current plain-text clipboard value.
 * @returns {string|null} The original Markdown or null for any other clipboard shape.
 */
export const getRichTextClipboardContent = (textRawData) => {
  const richClipboardData = getStoredRichClipboardData(textRawData)
  if (richClipboardData?.length !== 1 || richClipboardData[0]?.length !== 1) {
    return null
  }

  const richValue = richClipboardData[0][0]
  return richValue?.richText && typeof richValue.value === 'string'
    ? richValue.value
    : null
}

/**
 * This method gets the text and json data from the clipboard and from the local
 * storage. This is needed because we need the original metadata to be able to
 * restore the original format, but the clipboard only allows to store plain
 * text, html or images related mime types.
 * @param {*} event
 * @returns {object} An object with the textRawData and jsonRawData. The
 * textRawData is the plain text that is stored in the clipboard. The
 * jsonRawData is the rich json object with all the metadata needed to restore
 * the original data in the correct rich format.
 */
export const getRichClipboard = async (event) => {
  let textRawData

  if (typeof navigator.clipboard?.readtText !== 'undefined') {
    textRawData = await navigator.clipboard.readText()
  } else {
    textRawData = event.clipboardData.getData('text/plain')
  }

  const jsonRawData = getStoredRichClipboardData(textRawData)
  return { textRawData: textRawData.trim(), jsonRawData }
}

/**
 * DEPRECATED: Kept for backward compatibility where the clipboard API is not available.
 * Values should be an object with mime types as key and clipboard content for this type
 * as value. This allow add the same data with multiple representation to the clipboard.
 * We can have a row saved as tsv string or as json string. Values must be strings.
 * @param {object} values object of mime types -> clipboard content.
 */
export const setRichClipboard = (values) => {
  const listener = (e) => {
    e.preventDefault()
    e.stopPropagation()
    Object.entries(values).forEach(([type, content]) => {
      e.clipboardData.setData(type, content)
    })
  }
  document.addEventListener('copy', listener)
  try {
    document.execCommand('copy')
  } finally {
    document.removeEventListener('copy', listener)
  }
}
