// Same ASCII-only grammar as `rich_text_utils.py`: the backend must strip every URL trusted here.
const IMAGE_WITH_URL_REGEX =
  /!\[([^[\]\\]*(?:\\[^\n][^[\]\\]*)*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\] \t\n\r\f\v/\\()]*)\]\(([^() \t\n\r\f\v]*)\)/g

const BACKTICK_RUN_REGEX = /`+/g
// CommonMark 4.5: a fence is 3+ backticks or tildes indented by up to 3 spaces.
const FENCE_REGEX = /^ {0,3}(`{3,}|~{3,})/
const FENCE_CLOSE_TAIL_REGEX = /^[ \t]*\r?\n?$/
const LINE_REGEX = /[^\n]*\n|[^\n]+$/g

/**
 * Splits `content` into fenced code blocks and the text around them, like
 * `_iter_fence_segments` on the backend. Lines end at `\n` only, so both sides
 * agree on where a fence starts.
 */
function* iterFenceSegments(content) {
  let text = ''
  let code = ''
  let fenceChar = null
  let fenceLength = 0

  for (const line of content.match(LINE_REGEX) || []) {
    const match = FENCE_REGEX.exec(line)
    if (fenceChar === null) {
      if (match) {
        if (text) {
          yield [text, false]
          text = ''
        }
        fenceChar = match[1][0]
        fenceLength = match[1].length
        code += line
      } else {
        text += line
      }
    } else {
      code += line
      if (
        match &&
        match[1][0] === fenceChar &&
        match[1].length >= fenceLength &&
        FENCE_CLOSE_TAIL_REGEX.test(line.slice(match[0].length))
      ) {
        yield [code, true]
        code = ''
        fenceChar = null
      }
    }
  }

  if (text) yield [text, false]
  if (code) yield [code, true]
}

/**
 * A run of `n` backticks opens an inline code span that the next run of
 * exactly `n` backticks closes (CommonMark 6.1). Every run is matched at most
 * once, so this stays linear on pathological input.
 */
function* iterInlineCodeSegments(content) {
  const runs = []
  for (const match of content.matchAll(BACKTICK_RUN_REGEX)) {
    runs.push([match.index, match.index + match[0].length])
  }
  if (!runs.length) {
    yield [content, false]
    return
  }

  const byLength = new Map()
  runs.forEach(([start, end], index) => {
    const length = end - start
    if (!byLength.has(length)) byLength.set(length, [])
    byLength.get(length).push(index)
  })
  const nextPosition = new Map()

  let position = 0
  let index = 0
  while (index < runs.length) {
    const [start, end] = runs[index]
    const length = end - start
    const candidates = byLength.get(length)
    let cursor = nextPosition.get(length) || 0
    while (cursor < candidates.length && candidates[cursor] <= index) cursor++
    nextPosition.set(length, cursor)
    if (cursor < candidates.length) {
      const closing = candidates[cursor]
      nextPosition.set(length, cursor + 1)
      if (start > position) yield [content.slice(position, start), false]
      yield [content.slice(start, runs[closing][1]), true]
      position = runs[closing][1]
      index = closing + 1
    } else {
      index++
    }
  }

  if (position < content.length) yield [content.slice(position), false]
}

/**
 * Yields `[segment, isCode]` pairs covering `content` in order. Inside a fenced
 * block or an inline code span, image syntax is literal text: it must not be
 * rewritten, resolved or replaced by a placeholder. Mirrors
 * `iter_code_segments` on the backend.
 */
export function* iterCodeSegments(content) {
  for (const [segment, isCode] of iterFenceSegments(content)) {
    if (isCode) {
      yield [segment, true]
    } else {
      yield* iterInlineCodeSegments(segment)
    }
  }
}

/**
 * Applies `transform` to every non-code segment of `content` and leaves the
 * code segments untouched.
 */
export function mapOutsideCode(content, transform) {
  let result = ''
  for (const [segment, isCode] of iterCodeSegments(content)) {
    result += isCode ? segment : transform(segment)
  }
  return result
}

export function preprocessRichTextImages(content) {
  if (!content) return { content: content || '', nameMap: {} }
  const nameMap = {}
  const processed = mapOutsideCode(content, (segment) =>
    segment.replace(IMAGE_WITH_URL_REGEX, (match, alt, name, url) => {
      nameMap[url] = name
      return `![${alt}](${url})`
    })
  )
  return { content: processed, nameMap }
}

/**
 * Strips the URL from every `![alt][name](url)` outside code, except the URLs
 * `keepUrl` accepts.
 */
export function stripImageUrls(content, keepUrl = () => false) {
  if (!content) return content || ''
  return mapOutsideCode(content, (segment) =>
    segment.replace(IMAGE_WITH_URL_REGEX, (match, alt, name, url) =>
      keepUrl(url) ? match : `![${alt}][${name}]`
    )
  )
}

const IMAGE_REF_REGEX =
  /!\[([^[\]\\]*(?:\\[^\n][^[\]\\]*)*)\]\[[a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\] \t\n\r\f\v/\\()]*\]/g

// A sentinel standing in for an image on the surfaces that render none. It is a
// single character so it survives slicing and length maths as one unit, and
// `renderImagePlaceholders` swaps it for the icon after markdown-it has escaped
// the text. U+FE0E asks for text presentation, which keeps it monochrome in the
// places the sentinel is shown as-is (row history, a copied value).
export const IMAGE_PLACEHOLDER = '🖼︎'

// Markdown-it runs with `html: false`, so markup cannot be injected through the
// markdown source -- it would be escaped into literal text. The icon is swapped
// in afterwards instead, in the renderer, where escaping has already happened.
// Inter covers neither U+1F5BC nor any monochrome variant of it, so the glyph
// alone resolved to the colour emoji font on some pages and not others.
const IMAGE_PLACEHOLDER_ICON =
  '<i class="iconoir-media-image rich-text-image-placeholder" aria-hidden="true"></i>'

/**
 * Replaces every placeholder sentinel in rendered HTML with the icon markup.
 *
 * Runs on HTML markdown-it has already escaped, and the sentinel cannot appear
 * in escaped user text, so this introduces no injection surface.
 */
export function renderImagePlaceholders(html) {
  if (!html) return html || ''
  return html.split(IMAGE_PLACEHOLDER).join(IMAGE_PLACEHOLDER_ICON)
}

const imagePlaceholderFor = (alt) =>
  alt ? `${IMAGE_PLACEHOLDER} ${alt}` : IMAGE_PLACEHOLDER

export function stripUnresolvedImageRefs(content) {
  if (!content) return content || ''
  return mapOutsideCode(content, (segment) =>
    segment.replace(IMAGE_REF_REGEX, (match, alt) => imagePlaceholderFor(alt))
  )
}

export function replaceImagesWithPlaceholder(content) {
  if (!content) return content || ''
  const result = stripUnresolvedImageRefs(stripImageUrls(content))
  // Also replace plain markdown images `![alt](url)` with placeholder text.
  return mapOutsideCode(result, (segment) =>
    segment.replace(PLAIN_IMAGE_REGEX, (match, alt) => imagePlaceholderFor(alt))
  )
}

// External `![alt](url)`, only for the placeholder; no unbalanced `(` keeps it linear.
const PLAIN_IMAGE_REGEX =
  /!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\(((?:[^()]|\([^()]*\))*)\)/g

// An image token that starts but never closes before the end of the input, e.g.
// `![alt` or `![alt][name](url`. A complete token followed by anything does not
// match because the anchors require the end. The URL tails stop at an
// unbalanced `(` for the same reason as the regexes above: otherwise every `![`
// would scan to the end of the input.
const ALT_TAIL = String.raw`[^[\]\\\n]*(?:\\.[^[\]\\\n]*)*`
const PLAIN_URL_TAIL = String.raw`(?:[^()\n]|\([^()\n]*\))*(?:\([^()\n]*)?`
const UNFINISHED_IMAGE_TAIL_REGEX = new RegExp(
  String.raw`!\[${ALT_TAIL}(?:\]\[[^\]\n]*(?:\]\([^()\n]*)?|\]\(${PLAIN_URL_TAIL})?$`
)

/**
 * Drops an image token cut off at the end of `content`, e.g. after slicing a
 * value for a preview, so no half reference is left visible.
 */
export function trimUnfinishedImageRef(content) {
  if (!content) return content || ''
  return content.replace(UNFINISHED_IMAGE_TAIL_REGEX, '')
}

const SVG_EXTENSIONS = ['svg', 'svgz']

/**
 * Whether an uploaded user file can be embedded as an image in rich text. The
 * backend flags SVG uploads as `is_image: false` (no thumbnails, active content
 * neutralised), but rendering them through `<img>` is safe, so accept them too.
 * The extension comes from `name` (`<unique>_<hash>.<original_extension>`).
 */
export function isRenderableUserFile(userFile) {
  if (!userFile) return false
  if (userFile.is_image) return true
  const name = userFile.name || ''
  const dot = name.indexOf('.')
  if (dot === -1) return false
  return SVG_EXTENSIONS.includes(name.slice(dot + 1).toLowerCase())
}

// Characters a user file name's extension cannot contain for the stored
// reference `![alt][<name>_<hash>.<ext>]` to match.
const UNSAFE_EXTENSION_CHARS_REGEX = /[\]()\s/\\]/g

/**
 * Drops the characters the reference cannot carry from the extension of an
 * upload's name, e.g. `photo.png)` becomes `photo.png`. The backend derives the
 * stored extension from this name.
 */
export function sanitizeUploadFileName(name) {
  if (!name) return name || ''
  const dot = name.lastIndexOf('.')
  if (dot === -1) return name
  return (
    name.slice(0, dot + 1) +
    name.slice(dot + 1).replace(UNSAFE_EXTENSION_CHARS_REGEX, '')
  )
}

const IMAGE_TYPES_BY_EXTENSION = {
  apng: 'image/apng',
  avif: 'image/avif',
  bmp: 'image/bmp',
  gif: 'image/gif',
  ico: 'image/x-icon',
  jpeg: 'image/jpeg',
  jpg: 'image/jpeg',
  png: 'image/png',
  svg: 'image/svg+xml',
  webp: 'image/webp',
}

/**
 * The image MIME type to upload `file` as, or `null` when it is not an image.
 * The browser derives `file.type` from the extension, so `photo.png)` arrives
 * with an empty type; the sanitized extension decides then.
 */
export function imageUploadType(file) {
  if (!file) return null
  if (file.type) return file.type.startsWith('image/') ? file.type : null
  const name = sanitizeUploadFileName(file.name || '')
  const dot = name.lastIndexOf('.')
  if (dot === -1) return null
  return IMAGE_TYPES_BY_EXTENSION[name.slice(dot + 1).toLowerCase()] || null
}

/**
 * Whether a dropped or pasted file is worth uploading as an image. A file the
 * browser could not type (no extension, or `photo.png)`) may still be one, so
 * it is uploaded and the backend's `is_image` decides, like a misleading type.
 */
export function isImageUploadCandidate(file) {
  return Boolean(file) && (!file.type || file.type.startsWith('image/'))
}
