import {
  decodeQuotedGridCell,
  plainTextToMarkdown,
  plainTextToRichTextContent,
  richMarkdownToPlainText,
} from '@baserow/modules/core/editor/richTextClipboard'

describe('rich text clipboard conversion', () => {
  test('decodes a quoted grid cell including escaped quotes and CRLF', () => {
    expect(decodeQuotedGridCell('"first ""quoted""\r\n\r\nlast"')).toBe(
      'first "quoted"\n\nlast'
    )
    expect(decodeQuotedGridCell('not quoted')).toBeNull()
  })

  test('uses hard breaks when plain text has no empty paragraphs', () => {
    expect(plainTextToRichTextContent('first\r\nsecond')).toStrictEqual([
      { type: 'text', text: 'first' },
      { type: 'hardBreak' },
      { type: 'text', text: 'second' },
    ])
  })

  test('uses paragraphs when plain text contains empty lines', () => {
    expect(plainTextToRichTextContent('\nfirst\n\nlast\n')).toStrictEqual([
      { type: 'paragraph' },
      { type: 'paragraph', content: [{ type: 'text', text: 'first' }] },
      { type: 'paragraph' },
      { type: 'paragraph', content: [{ type: 'text', text: 'last' }] },
      { type: 'paragraph' },
    ])
  })

  test('round-trips plain newlines through the Markdown storage form', () => {
    const plainText = '\nfirst\n\n\nlast\n'
    const markdown = plainTextToMarkdown(plainText)

    expect(markdown).toBe(
      '&nbsp;\n\nfirst\n\n&nbsp;\n\n&nbsp;\n\nlast\n\n&nbsp;'
    )
    expect(richMarkdownToPlainText(markdown)).toBe(plainText)
  })

  test('removes rich hard-break syntax when targeting plain text', () => {
    expect(richMarkdownToPlainText('first  \nsecond')).toBe('first\nsecond')
  })
})
