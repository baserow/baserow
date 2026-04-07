/**
 * Extracts a list of files from a dom event when it is triggered. Supports both input
 * and drag and drop file uploads.
 *
 * @param event
 * @returns {null}
 */
export function getFilesFromEvent(event) {
  if (event.target?.files) {
    // Files via the file upload input.
    return event.target.files
  }

  if (event.dataTransfer) {
    // Files via drag and drop.
    return event.dataTransfer.files
  }

  return []
}

/**
 * Originally from
 * https://stackoverflow.com/questions/15900485/correct-way-to-convert-size-in-bytes-to-kb-mb-gb-in-javascript
 *
 * Converts an integer representing the amount of bytes to a human readable format.
 * Where for example 1024 will end up in 1KB.
 */
export function formatFileSize($i18n, bytes) {
  if (bytes === 0) return '0 ' + $i18n.t(`rowEditFieldFile.sizes.0`)
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  const float = parseFloat((bytes / k ** i).toFixed(2)).toLocaleString(
    $i18n.locale
  )
  return float + ' ' + $i18n.t(`rowEditFieldFile.sizes.${i}`)
}
