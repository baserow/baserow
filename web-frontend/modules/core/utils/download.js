/**
 * Adds the name to save the file as to the URL of the file. The storage serving
 * it then answers with that name as the attachment.
 */
export function getDownloadHref(url, filename) {
  const href = new URL(url)
  href.searchParams.set('dl', filename)
  return href.toString()
}

/**
 * Clicks a temporary, hidden anchor, which is returned so that it can be removed.
 * Its click doesn't propagate, so that a modal or context it's in stays open.
 */
function clickTemporaryAnchor(href, filename, target) {
  const anchor = document.createElement('a')
  anchor.style = 'display: none'
  anchor.href = href
  if (target) {
    anchor.target = target
  }
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.onclick = (event) => {
    event.stopPropagation()
  }
  anchor.click()
  return anchor
}

/**
 * Fetches the file and saves the response as a blob, for the storages that don't
 * answer with an attachment. A failed response is thrown, so that an error isn't
 * saved as the file.
 */
export async function downloadViaXhr(url, filename) {
  // We are using fetch here to avoid extra header as we need to add them to CORS
  // later.
  const response = await fetch(url, {
    // Needed to prevent chrome not sending the Origin header in the actual GET
    // request. Without this header S3 will not respond with the correct CORS
    // headers.
    cache: 'no-store',
  })
  if (!response.ok) {
    throw new Error(`The file couldn't be downloaded (${response.status}).`)
  }
  const blob = await response.blob()
  const data = window.URL.createObjectURL(blob)

  const anchor = clickTemporaryAnchor(data, filename, '_blank')

  setTimeout(function () {
    document.body.removeChild(anchor)
    // Release the resource after triggering the download.
    window.URL.revokeObjectURL(data)
  }, 500)
}

/**
 * Saves the file of the URL as `filename`, the way `DownloadLink` does, for a URL
 * that is only known after the click, for example because it's fetched first.
 *
 * A new tab can only be opened while the user's click still counts, which it may
 * no longer do after the URL was fetched. Then the file is downloaded from this
 * tab instead: it's an attachment, so the page stays.
 */
export async function triggerDownload(url, filename, { viaXhr = false } = {}) {
  if (viaXhr) {
    await downloadViaXhr(url, filename)
    return
  }
  const target = navigator.userActivation?.isActive !== false ? '_blank' : null
  const anchor = clickTemporaryAnchor(
    getDownloadHref(url, filename),
    filename,
    target
  )
  document.body.removeChild(anchor)
}
