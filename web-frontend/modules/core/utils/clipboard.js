/**
 * Copies the given text to the browser clipboard.
 * @param {string} text
 */
export const copyToClipboard = (text) => {
  navigator.clipboard.writeText(text)
}
