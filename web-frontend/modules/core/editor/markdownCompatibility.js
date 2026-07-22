import { Extension } from '@tiptap/core'
import { Fragment } from '@tiptap/pm/model'

// Marked can produce structurally incomplete JSON for valid but empty Markdown
// constructs. Fit that JSON to the active ProseMirror schema before it reaches the
// editor, and report any lossy recovery so the caller can retain the source as text.
const createMarks = (schema, state, markJson = []) =>
  markJson.flatMap(({ type, attrs }) => {
    const markType = schema.marks[type]
    if (!markType) {
      state.lossy = true
      return []
    }
    try {
      return [markType.create(attrs)]
    } catch {
      state.lossy = true
      return []
    }
  })

const wrapChildForContentMatch = (schema, state, match, child) => {
  const wrapperType = match.defaultType
  if (!wrapperType) {
    return null
  }

  let wrapper = wrapperType.createAndFill(null, child)
  if (wrapper) {
    return wrapper
  }

  const paragraphType = schema.nodes.paragraph
  if (!paragraphType || !child.textContent) {
    return null
  }

  const paragraph = paragraphType.createAndFill(
    null,
    schema.text(child.textContent)
  )
  wrapper = paragraph && wrapperType.createAndFill(null, paragraph)
  if (wrapper) {
    state.lossy = true
  }
  return wrapper ?? null
}

const fitContent = (schema, state, nodeType, children) => {
  const fitted = []
  let match = nodeType.contentMatch

  for (let index = 0; index < children.length; index++) {
    const child = children[index]
    const directMatch = match.matchType(child.type)
    if (directMatch) {
      fitted.push(child)
      match = directMatch
      continue
    }

    if (child.isInline && match.defaultType?.isTextblock) {
      const inline = [child]
      while (children[index + 1]?.isInline) {
        inline.push(children[++index])
      }
      const wrapped = match.defaultType.createAndFill(
        null,
        Fragment.from(inline)
      )
      const wrappedMatch = wrapped && match.matchType(wrapped.type)
      if (wrappedMatch) {
        fitted.push(wrapped)
        match = wrappedMatch
      }
      continue
    }

    const wrapped = wrapChildForContentMatch(schema, state, match, child)
    const wrappedMatch = wrapped && match.matchType(wrapped.type)
    if (wrappedMatch) {
      fitted.push(wrapped)
      match = wrappedMatch
    } else {
      state.lossy = true
    }
  }

  return Fragment.from(fitted)
}

const normalizeNode = (schema, state, nodeJson) => {
  const nodeType = schema.nodes[nodeJson?.type]
  if (!nodeType) {
    state.lossy = true
    return null
  }

  const marks = createMarks(schema, state, nodeJson.marks)
  if (nodeType.isText) {
    return nodeJson.text ? schema.text(nodeJson.text, marks) : null
  }

  let children = (nodeJson.content ?? []).flatMap((child) => {
    const normalized = normalizeNode(schema, state, child)
    return normalized ? [normalized] : []
  })
  if (
    nodeType.name === 'paragraph' &&
    children.length === 1 &&
    children[0].isText &&
    ['&nbsp;', '\u00a0'].includes(children[0].text)
  ) {
    children = []
  }
  const content = fitContent(schema, state, nodeType, children)

  const normalized = nodeType.createAndFill(nodeJson.attrs, content, marks)
  if (normalized) {
    return normalized
  }
  if (children.length > 0) {
    state.lossy = true
  }
  return nodeType.createAndFill(nodeJson.attrs, null, marks)
}

const markdownAsPlainTextDocument = (schema, markdown) => {
  const paragraphType = schema.nodes.paragraph
  const hardBreakType = schema.nodes.hardBreak
  const content = []
  const lines = markdown.replace(/\r\n?/g, '\n').split('\n')

  lines.forEach((line, index) => {
    if (line) {
      content.push(schema.text(line))
    }
    if (index < lines.length - 1 && hardBreakType) {
      content.push(hardBreakType.create())
    }
  })

  const paragraph = paragraphType.createAndFill(null, Fragment.from(content))
  return schema.topNodeType.createAndFill(null, paragraph).toJSON()
}

export const normalizeMarkdownDocument = (schema, document, markdown = '') => {
  try {
    const state = { lossy: false }
    const normalized = normalizeNode(schema, state, document)
    if (state.lossy || !normalized || normalized.type !== schema.topNodeType) {
      return markdownAsPlainTextDocument(schema, markdown)
    }
    normalized.check()
    return normalized.toJSON()
  } catch {
    return markdownAsPlainTextDocument(schema, markdown)
  }
}

const getInlineCodeSerializationAttrs = (text) => {
  const longestBacktickRun = Math.max(
    0,
    ...(text.match(/`+/g) ?? []).map(({ length }) => length)
  )
  return {
    markdownDelimiter: '`'.repeat(longestBacktickRun + 1),
    markdownPadding:
      longestBacktickRun > 0 ||
      (text.startsWith(' ') && text.endsWith(' ') && text.trim().length > 0),
  }
}

const encodeInlineCodeText = (text) =>
  // The official serializer moves boundary whitespace outside every mark. Numeric
  // entities keep it inside code spans; ampersands are encoded first so literal
  // entity-looking code remains byte-for-byte text after the single decode pass.
  text
    .replaceAll('&', '&#38;')
    .replace(/^\s+|\s+$/g, (whitespace) =>
      [...whitespace]
        .map((character) => `&#${character.codePointAt(0)};`)
        .join('')
    )

export const prepareMarkdownDocumentForSerialization = (node) => {
  const prepared = { ...node }
  if (node.type === 'text' && node.marks?.length) {
    const hasCodeMark = node.marks.some(({ type }) => type === 'code')
    if (hasCodeMark) {
      prepared.text = encodeInlineCodeText(node.text ?? '')
    }
    prepared.marks = node.marks.map((mark) =>
      mark.type === 'code'
        ? {
            ...mark,
            attrs: {
              ...mark.attrs,
              ...getInlineCodeSerializationAttrs(node.text ?? ''),
            },
          }
        : mark
    )
  }
  if (node.content?.length) {
    prepared.content = node.content.map(prepareMarkdownDocumentForSerialization)
  }
  return prepared
}

const configuredMarkdownManagers = new WeakSet()

export const configureMarkdownSerializerCompatibility = (manager) => {
  if (configuredMarkdownManagers.has(manager)) {
    return
  }
  configuredMarkdownManagers.add(manager)

  // TipTap's serializer does not escape block syntax when a text node follows a
  // hard break. Escaping these punctuation characters everywhere is canonical but
  // guarantees that literal text cannot become a heading, list, quote, or table.
  const escapeMarkdownSyntax = manager.escapeMarkdownSyntax.bind(manager)
  manager.escapeMarkdownSyntax = (text) =>
    escapeMarkdownSyntax(text).replace(/([#>+\-=.|])/g, '\\$1')
}

export const MarkdownInputCapture = Extension.create({
  name: 'markdownInputCapture',
  priority: 110,
  addStorage() {
    return { initialContent: undefined }
  },
  onBeforeCreate() {
    // This runs before the official Markdown extension (priority 100), which
    // replaces the initial string with parsed JSON.
    this.storage.initialContent = this.editor.options.content
  },
})

export const MarkdownDocumentCompatibility = Extension.create({
  name: 'markdownDocumentCompatibility',
  priority: 90,
  onBeforeCreate() {
    if (!this.editor.markdown) {
      return
    }

    configureMarkdownSerializerCompatibility(this.editor.markdown)

    // This runs after the official Markdown extension, so both its initial parse
    // and all later parse/serialize calls share the same compatibility boundary.
    const originalParse = this.editor.markdown.parse.bind(this.editor.markdown)
    const originalSerialize = this.editor.markdown.serialize.bind(
      this.editor.markdown
    )
    this.editor.markdown.parse = (markdown) =>
      normalizeMarkdownDocument(
        this.editor.schema,
        originalParse(markdown),
        markdown
      )
    this.editor.markdown.serialize = (document) =>
      originalSerialize(prepareMarkdownDocumentForSerialization(document))

    const initialMarkdown =
      this.editor.storage.markdownInputCapture?.initialContent
    if (
      this.editor.options.contentType === 'markdown' &&
      typeof initialMarkdown === 'string' &&
      typeof this.editor.options.content !== 'string'
    ) {
      this.editor.options.content = normalizeMarkdownDocument(
        this.editor.schema,
        this.editor.options.content,
        initialMarkdown
      )
    }
  },
})

const parseLiteralMarkdownHtml = (token, helpers) => {
  const raw = (token.raw ?? token.text ?? '').replace(/\s+$/, '')
  const escapedHtml = raw.replaceAll('<', '&lt;').replaceAll('>', '&gt;')
  return helpers.parseInline(helpers.tokenizeInline(escapedHtml))
}

export const LiteralMarkdownHtml = Extension.create({
  name: 'literalMarkdownHtml',
  markdownTokenName: 'html',
  parseMarkdown: parseLiteralMarkdownHtml,
})

const INLINE_HTML_REGEXP =
  /^(?:<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\?[\s\S]*?\?>|<![A-Z][^>]*>|<\/?[A-Za-z][\w-]*(?:\s[^>]*)?\/?>)/

export const LiteralInlineMarkdownHtml = Extension.create({
  name: 'literalInlineMarkdownHtml',
  markdownTokenizer: {
    name: 'literalInlineMarkdownHtml',
    level: 'inline',
    start(source) {
      return source.indexOf('<')
    },
    tokenize(source) {
      const match = source.match(INLINE_HTML_REGEXP)
      if (!match) {
        return undefined
      }
      return {
        type: 'literalInlineMarkdownHtml',
        raw: match[0],
        text: match[0],
      }
    },
  },
  parseMarkdown: parseLiteralMarkdownHtml,
})

const decodeNumericEntity = (raw) => {
  const isHex = raw[2]?.toLowerCase() === 'x'
  const value = parseInt(raw.slice(isHex ? 3 : 2, -1), isHex ? 16 : 10)
  try {
    return value > 0 && value <= 0x10ffff
      ? String.fromCodePoint(value)
      : '\ufffd'
  } catch {
    return '\ufffd'
  }
}

export const decodeInlineCodeText = (text) =>
  text.replace(/&#(?:x[\da-f]+|\d+);/gi, decodeNumericEntity)

const NUMERIC_ENTITY_REGEXP = /&#(?:x[\da-f]+|\d+);/i

export const LegacyNumericHtmlEntity = Extension.create({
  name: 'legacyNumericHtmlEntity',
  markdownTokenizer: {
    name: 'legacyNumericHtmlEntity',
    level: 'inline',
    start(source) {
      return source.search(NUMERIC_ENTITY_REGEXP)
    },
    tokenize(source) {
      const match = source.match(
        new RegExp(`^${NUMERIC_ENTITY_REGEXP.source}`, 'i')
      )
      if (!match) {
        return undefined
      }
      return {
        type: 'legacyNumericHtmlEntity',
        raw: match[0],
        text: decodeNumericEntity(match[0]),
      }
    },
  },
  parseMarkdown(token, helpers) {
    return helpers.createTextNode(token.text)
  },
})
