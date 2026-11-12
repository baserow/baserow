/**
 * Copies the given text to the browser clipboard.
 * @param {string} text
 * @returns {Promise<void>} Rejects when the text couldn't be copied.
 */
export const copyToClipboard = (text) => navigator.clipboard.writeText(text)
