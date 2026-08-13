// Alt text: anything except unescaped `[`/`]`, allowing backslash escapes.
// Deliberately linear (no nested quantifiers) to stay ReDoS-safe. The name must
// look like `<name>_<hash>.<ext>` and may not contain path separators, so it can
// never escape the user files directory.
const IMAGE_WITH_URL_REGEX =
  /!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\]+)\]\(([^)]+)\)/g

export function preprocessRichTextImages(content) {
  if (!content) return { content: content || '', nameMap: {} }
  const nameMap = {}
  const processed = content.replace(
    IMAGE_WITH_URL_REGEX,
    (match, alt, name, url) => {
      nameMap[url] = name
      return `![${alt}](${url})`
    }
  )
  return { content: processed, nameMap }
}

export function stripImageUrls(content) {
  if (!content) return content || ''
  return content.replace(
    IMAGE_WITH_URL_REGEX,
    (match, alt, name) => `![${alt}][${name}]`
  )
}

const IMAGE_REF_REGEX =
  /!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\[[a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\]+\]/g

export function stripUnresolvedImageRefs(content) {
  if (!content) return content || ''
  return content.replace(IMAGE_REF_REGEX, (match, alt) => {
    return alt ? `🖼 ${alt}` : '🖼'
  })
}

export function replaceImagesWithPlaceholder(content) {
  if (!content) return content || ''
  let result = stripUnresolvedImageRefs(stripImageUrls(content))
  // Also replace plain markdown images `![alt](url)` with placeholder text.
  result = result.replace(PLAIN_IMAGE_REGEX, (match, alt) => {
    return alt ? `🖼 ${alt}` : '🖼'
  })
  return result
}

// Plain markdown images `![alt](url)` that are not Baserow uploads. Cannot
// match the Baserow form because there `]` is followed by `[name]`, not `(`.
const PLAIN_IMAGE_REGEX = /!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\(([^)]*)\)/g

// An image token that starts but never closes before the end of the input, e.g.
// `![alt` or `![alt][name](url`. A complete token followed by anything does not
// match because the anchors require the end.
const ALT_TAIL = String.raw`[^[\]\\\n]*(?:\\.[^[\]\\\n]*)*`
const UNFINISHED_IMAGE_TAIL_REGEX = new RegExp(
  String.raw`!\[${ALT_TAIL}(?:\]\[[^\]\n]*(?:\]\([^)\n]*)?|\]\([^)\n]*)?$`
)

/**
 * Drops an image token cut off at the end of `content`, e.g. after slicing a
 * value for a preview, so no half reference is left visible.
 */
export function trimUnfinishedImageRef(content) {
  if (!content) return content || ''
  return content.replace(UNFINISHED_IMAGE_TAIL_REGEX, '')
}

const SAFE_IMAGE_SCHEMES = new Set(['http:', 'https:', ''])

/**
 * Whether a plain `![alt](url)` image may render as an image. Mirrors the
 * backend: scheme compared case insensitively, empty (relative) allowed. Shared
 * with the image extension so parser and serializer cannot disagree.
 */
export function isSafeImageSrc(url) {
  if (!url) return url === ''
  try {
    const scheme = url.includes(':')
      ? url.slice(0, url.indexOf(':') + 1).toLowerCase()
      : ''
    return SAFE_IMAGE_SCHEMES.has(scheme)
  } catch {
    // malformed URL — not safe to render as an image
    return false
  }
}

/**
 * Rewrites plain markdown images with unsafe protocols (javascript:, data:,
 * etc.) into links. Images with http/https URLs pass through unchanged.
 */
export function validateExternalImageProtocols(content) {
  if (!content) return content || ''
  return content.replace(PLAIN_IMAGE_REGEX, (match, alt, url) => {
    return isSafeImageSrc(url) ? match : `[${alt}](${url})`
  })
}

const SVG_EXTENSIONS = ['svg', 'svgz']

/**
 * Whether an uploaded user file can be embedded as an image in rich text. The
 * backend flags SVG uploads as `is_image: false` (no thumbnails, active content
 * neutralised), but rendering them through `<img>` is safe, so accept them too.
 * Mirrors `is_renderable_user_file` on the backend: only `original_extension`
 * is consulted so the two sides can't disagree on a file.
 */
export function isRenderableUserFile(userFile) {
  if (!userFile) return false
  if (userFile.is_image) return true
  const extension = (userFile.original_extension || '').toLowerCase()
  return SVG_EXTENSIONS.includes(extension)
}
