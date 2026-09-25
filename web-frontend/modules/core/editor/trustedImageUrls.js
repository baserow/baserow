// URLs the rich text editor may load as `<img src>`. Only URLs that came from
// Baserow itself are registered: a value the backend resolved
// (`![alt][name](url)`), an upload response, or a grid clipboard value (which
// the backend also produced). Anything else, e.g. pasted HTML carrying a
// `data-user-file-name` next to a foreign `src`, renders as a placeholder until
// the value is saved and the backend resolves the name itself.
//
// Module level so every editor on the page shares it; capped so a long session
// does not grow it without bound. A `Map` keeps insertion order, which makes it
// a small LRU: a hit is moved to the end, the oldest entry is evicted first.
import { preprocessRichTextImages } from '@baserow/modules/core/editor/richTextImageUtils'

export const MAX_TRUSTED_IMAGE_URLS = 1000

const trustedUrls = new Map()

const isClient = () => typeof window !== 'undefined'

export function registerTrustedImageUrl(url) {
  if (!url || typeof url !== 'string' || !isClient()) {
    return
  }
  trustedUrls.delete(url)
  trustedUrls.set(url, true)
  while (trustedUrls.size > MAX_TRUSTED_IMAGE_URLS) {
    trustedUrls.delete(trustedUrls.keys().next().value)
  }
}

export function isTrustedImageUrl(url) {
  if (!url || !trustedUrls.has(url)) {
    return false
  }
  trustedUrls.delete(url)
  trustedUrls.set(url, true)
  return true
}

/**
 * Registers the URL of every resolved `![alt][name](url)` reference outside
 * code in a Markdown value that came from the backend.
 */
export function registerTrustedImageUrlsFromMarkdown(value) {
  if (typeof value !== 'string' || !value || !isClient()) {
    return
  }
  const { nameMap } = preprocessRichTextImages(value)
  Object.keys(nameMap).forEach(registerTrustedImageUrl)
}

export function clearTrustedImageUrls() {
  trustedUrls.clear()
}
