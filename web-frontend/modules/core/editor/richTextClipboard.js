const normalizeNewlines = (text) => text.replace(/\r\n?/g, '\n')

const RICH_TEXT_EDITOR_CLIPBOARD_KEY = 'baserow.richTextEditorClipboardData'

export const rememberRichTextEditorClipboard = (text) => {
  try {
    localStorage.setItem(RICH_TEXT_EDITOR_CLIPBOARD_KEY, text)
  } catch {
    // Clipboard serialization must keep working when storage is unavailable.
  }
}

export const isRichTextEditorClipboard = (text) => {
  try {
    const copiedText = localStorage.getItem(RICH_TEXT_EDITOR_CLIPBOARD_KEY)
    if (
      copiedText !== null &&
      normalizeNewlines(copiedText) === normalizeNewlines(text)
    ) {
      return true
    }
    localStorage.removeItem(RICH_TEXT_EDITOR_CLIPBOARD_KEY)
  } catch {
    // A missing marker means the paste must follow the external plain-text path.
  }
  return false
}

const needsEmptyParagraphs = (text) =>
  text.startsWith('\n') || text.endsWith('\n') || text.includes('\n\n')

const plainTextToParagraphContent = (text) =>
  text.split('\n').map((line) => ({
    type: 'paragraph',
    ...(line ? { content: [{ type: 'text', text: line }] } : {}),
  }))

export const decodeQuotedGridCell = (text) => {
  if (!text.startsWith('"') || !text.endsWith('"')) {
    return null
  }

  return normalizeNewlines(text.slice(1, -1).replaceAll('""', '"'))
}

export const plainTextToRichTextContent = (text) => {
  const normalized = normalizeNewlines(text)
  if (needsEmptyParagraphs(normalized)) {
    return plainTextToParagraphContent(normalized)
  }

  const lines = normalized.split('\n')
  const content = []

  lines.forEach((line, index) => {
    if (line) {
      content.push({ type: 'text', text: line })
    }
    if (index < lines.length - 1) {
      content.push({ type: 'hardBreak' })
    }
  })

  return content
}

export const plainTextToMarkdown = (text) => {
  const normalized = normalizeNewlines(text || '')
  if (!normalized || !needsEmptyParagraphs(normalized)) {
    return normalized.replaceAll('\n', '  \n')
  }
  return normalized
    .split('\n')
    .map((line) => line || '&nbsp;')
    .join('\n\n')
}

const NBSP = String.fromCharCode(160)
const EMPTY_PARAGRAPH_SENTINELS = ['&nbsp;', NBSP]

// Inverse of plainTextToMarkdown: drop the empty-paragraph sentinels and hard breaks.
export const richMarkdownToPlainText = (markdown) =>
  normalizeNewlines(markdown || '')
    .split('\n\n')
    .map((block) =>
      EMPTY_PARAGRAPH_SENTINELS.includes(block)
        ? ''
        : block.replaceAll('  \n', '\n')
    )
    .join('\n')
