// Alt text: anything except unescaped `[`/`]`, allowing backslash escapes.
// Deliberately linear (no nested quantifiers) to stay ReDoS-safe. The name must
// look like `<name>_<hash>.<ext>` and may not contain path separators, so it can
// never escape the user files directory.
const IMAGE_WITH_URL_REGEX =
  /!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\[([a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\()]+)\]\(([^)]*)\)/g

// A fenced code block opens with three or more backticks or tildes, indented
// by up to three spaces (CommonMark 4.5).
const FENCE_REGEX = /^ {0,3}(`{3,}|~{3,})/
const BACKTICK_RUN_REGEX = /`+/g

function* iterFenceSegments(content) {
  const lines = content.split(/(?<=\n)/)
  let text = []
  let code = []
  let fenceChar = null
  let fenceLength = 0

  for (const line of lines) {
    const match = FENCE_REGEX.exec(line)
    if (fenceChar === null) {
      if (match) {
        if (text.length) {
          yield [text.join(''), false]
          text = []
        }
        fenceChar = match[1][0]
        fenceLength = match[1].length
        code.push(line)
      } else {
        text.push(line)
      }
    } else {
      code.push(line)
      if (
        match &&
        match[1][0] === fenceChar &&
        match[1].length >= fenceLength &&
        line.slice(match[0].length).trim() === ''
      ) {
        yield [code.join(''), true]
        code = []
        fenceChar = null
      }
    }
  }

  if (text.length) yield [text.join(''), false]
  if (code.length) yield [code.join(''), true]
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

export function stripImageUrls(content) {
  if (!content) return content || ''
  return mapOutsideCode(content, (segment) =>
    segment.replace(
      IMAGE_WITH_URL_REGEX,
      (match, alt, name) => `![${alt}][${name}]`
    )
  )
}

const IMAGE_REF_REGEX =
  /!\[([^[\]\\]*(?:\\.[^[\]\\]*)*)\]\[[a-zA-Z0-9]+_[a-zA-Z0-9]+\.[^\]\s/\\()]+\]/g

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

/**
 * Rewrites every plain markdown image `![alt](url)` into a link `[alt](url)`.
 *
 * Rich text images are Baserow user files only. An external image would be
 * fetched by every reader of a public view from a host the workspace does not
 * control, which leaks reader IPs and lets the remote content be swapped after
 * the fact. Degrading to a link keeps the URL visible without loading it.
 *
 * Mirrors `demote_external_images_to_links` on the backend.
 */
export function demoteExternalImagesToLinks(content) {
  if (!content) return content || ''
  return mapOutsideCode(content, (segment) =>
    segment.replace(PLAIN_IMAGE_REGEX, (match, alt, url) => `[${alt}](${url})`)
  )
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
