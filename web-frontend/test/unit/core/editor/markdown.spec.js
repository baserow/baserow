import { Editor } from '@tiptap/core'

import {
  createRichTextEditorExtensions,
  parseMarkdownClipboard,
  serializeMarkdownClipboard,
} from '@baserow/modules/core/editor/richTextExtensions'
import { createMention } from '@baserow/modules/core/editor/mention'
import { parseMarkdown } from '@baserow/modules/core/editor/markdown'

const paragraph = (text) => ({
  type: 'paragraph',
  ...(text === undefined ? {} : { content: [{ type: 'text', text }] }),
})

function createEditor(content, { users = null } = {}) {
  const extensions = createRichTextEditorExtensions()
  if (users !== null) {
    extensions.push(createMention({ users }))
  }
  return new Editor({
    extensions,
    content,
    contentType: typeof content === 'string' ? 'markdown' : 'json',
  })
}

function reopen(editor, options) {
  const markdown = editor.getMarkdown()
  editor.destroy()
  return { editor: createEditor(markdown, options), markdown }
}

describe('official TipTap Markdown integration', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  test('preserves an empty line after saving and reopening', () => {
    const document = {
      type: 'doc',
      content: [paragraph('A'), paragraph(), paragraph('B')],
    }
    editor = createEditor(document)

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(reopened.markdown).toBe('A\n\n\n\nB')
    expect(editor.getJSON()).toStrictEqual(document)
  })

  test('preserves consecutive and boundary empty lines', () => {
    const document = {
      type: 'doc',
      content: [
        paragraph(),
        paragraph('A'),
        paragraph(),
        paragraph(),
        paragraph('B'),
        paragraph(),
      ],
    }
    editor = createEditor(document)

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(reopened.markdown).toBe('&nbsp;\n\nA\n\n\n\n&nbsp;\n\nB\n\n&nbsp;')
    expect(editor.getJSON()).toStrictEqual(document)
  })

  test.each([
    ['leading', [paragraph(), paragraph('A')], '&nbsp;\n\nA'],
    ['trailing', [paragraph('A'), paragraph()], 'A\n\n&nbsp;'],
  ])(
    'a %s empty paragraph survives whitespace-trimming storage',
    (position, content, expectedMarkdown) => {
      const document = { type: 'doc', content }
      editor = createEditor(document)

      const reopened = reopen(editor)
      editor = reopened.editor

      expect(reopened.markdown).toBe(expectedMarkdown)
      // The backend trims boundary whitespace, so none may carry meaning.
      expect(reopened.markdown).toBe(reopened.markdown.trim())
      expect(editor.getJSON()).toStrictEqual(document)
    }
  )

  test.each([
    ['inline punctuation', 'Price is 3.50 today. See item #4 and A+B=C now.'],
    ['number at line start', '3.50 each'],
    ['hashtag without space', '#4 items'],
    ['dash without space', '-dashed'],
  ])('never escapes %s', (name, text) => {
    const document = { type: 'doc', content: [paragraph(text)] }
    editor = createEditor(document)

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(reopened.markdown).toBe(text)
    expect(editor.getJSON()).toStrictEqual(document)
  })

  test.each([
    ['heading', '# not a heading', '\\# not a heading'],
    ['bullet', '- not a list', '\\- not a list'],
    ['ordered', '1. not a list', '1\\. not a list'],
    ['blockquote', '> not a quote', '&gt; not a quote'],
    ['horizontal rule', '---', '\\---'],
  ])(
    'escapes a literal %s at the start of a paragraph',
    (name, text, expectedMarkdown) => {
      const document = { type: 'doc', content: [paragraph(text)] }
      editor = createEditor(document)

      const reopened = reopen(editor)
      editor = reopened.editor

      expect(reopened.markdown).toBe(expectedMarkdown)
      expect(editor.getJSON()).toStrictEqual(document)
    }
  )

  test.each([
    ['bullet', '- not a list', 'first  \n\\- not a list'],
    ['setext underline', '===', 'first  \n\\==='],
  ])(
    'escapes a literal %s after a hard break',
    (name, text, expectedMarkdown) => {
      const document = {
        type: 'doc',
        content: [
          {
            type: 'paragraph',
            content: [
              { type: 'text', text: 'first' },
              { type: 'hardBreak' },
              { type: 'text', text },
            ],
          },
        ],
      }
      editor = createEditor(document)

      const reopened = reopen(editor)
      editor = reopened.editor

      expect(reopened.markdown).toBe(expectedMarkdown)
      expect(editor.getJSON()).toStrictEqual(document)
    }
  )

  test('keeps inline code content verbatim at a line start', () => {
    const document = {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: '- item', marks: [{ type: 'code' }] },
          ],
        },
      ],
    }
    editor = createEditor(document)

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(reopened.markdown).toBe('`- item`')
    expect(editor.getJSON()).toStrictEqual(document)
  })

  test('adjacent bullet lists alternate markers and stay separate', () => {
    const bulletList = (text) => ({
      type: 'bulletList',
      content: [{ type: 'listItem', content: [paragraph(text)], attrs: {} }],
    })
    editor = createEditor({
      type: 'doc',
      content: [
        bulletList('a'),
        bulletList('b'),
        paragraph('between'),
        bulletList('c'),
      ],
    })

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(reopened.markdown).toBe('- a\n\n* b\n\nbetween\n\n- c')
    expect(editor.getJSON().content.map(({ type }) => type)).toStrictEqual([
      'bulletList',
      'bulletList',
      'paragraph',
      'bulletList',
    ])
  })

  test('preserves empty lines inside blockquotes', () => {
    const document = {
      type: 'doc',
      content: [
        {
          type: 'blockquote',
          content: [paragraph('A'), paragraph(), paragraph('B')],
        },
      ],
    }
    editor = createEditor(document)

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(editor.getJSON()).toStrictEqual(document)
  })

  test('keeps single newlines as hard breaks', () => {
    editor = createEditor('first\nsecond')

    expect(editor.getJSON()).toStrictEqual({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'first' },
            { type: 'hardBreak' },
            { type: 'text', text: 'second' },
          ],
        },
      ],
    })
    expect(editor.getMarkdown()).toBe('first  \nsecond')
  })

  test('does not turn raw Markdown HTML into editor DOM', () => {
    editor = createEditor('<script>alert("unsafe")</script>')

    expect(editor.getHTML()).not.toContain('<script>')
  })

  test('round-trips the existing supported Markdown syntax', () => {
    const markdown = [
      '# Heading',
      '',
      '**bold** _italic_ ~~strike~~ [link](https://example.com)',
      '',
      '- bullet',
      '- list',
      '',
      '1. ordered',
      '2. list',
      '',
      '- [x] done',
      '- [ ] pending',
      '',
      '> quote',
      '',
      '```js',
      'const value = 1',
      '',
      'return value',
      '```',
      '',
      '---',
    ].join('\n')
    editor = createEditor(markdown)
    const parsed = editor.getJSON()

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(editor.getJSON()).toStrictEqual(parsed)
  })

  test('round-trips mentions without storing display names in Markdown', () => {
    const users = [{ user_id: 1, name: 'Jane Doe' }]
    editor = createEditor('Hello @1', { users })

    expect(editor.getHTML()).toContain('@Jane Doe')
    expect(editor.getMarkdown()).toBe('Hello @1')

    const reopened = reopen(editor, { users })
    editor = reopened.editor
    expect(editor.getHTML()).toContain('@Jane Doe')
    expect(editor.getMarkdown()).toBe('Hello @1')
  })

  test('parses and serializes Markdown on the plain-text clipboard', () => {
    editor = createEditor('')

    const slice = parseMarkdownClipboard(editor, '**bold**\nsecond line', false)

    expect(slice.content.toJSON()).toStrictEqual([
      {
        type: 'paragraph',
        content: [
          { type: 'text', marks: [{ type: 'bold' }], text: 'bold' },
          { type: 'hardBreak' },
          { type: 'text', text: 'second line' },
        ],
      },
    ])
    expect(serializeMarkdownClipboard(editor, slice)).toBe(
      '**bold**  \nsecond line'
    )
    expect(parseMarkdownClipboard(editor, '**bold**', true)).toBeNull()
  })
})

describe('rich-text Markdown previews', () => {
  test('renders empty lines using the official Markdown document model', () => {
    const html = parseMarkdown('A\n\n\n\nB')
    const document = new DOMParser().parseFromString(html, 'text/html')
    const paragraphs = [...document.querySelectorAll('p')]

    expect(paragraphs).toHaveLength(3)
    expect(paragraphs.map((element) => element.textContent)).toStrictEqual([
      'A',
      '\u00a0',
      'B',
    ])
  })

  test('does not invent paragraphs for blank lines inside code blocks', () => {
    const html = parseMarkdown('```\nA\n\nB\n```')
    const document = new DOMParser().parseFromString(html, 'text/html')

    expect(document.querySelectorAll('pre')).toHaveLength(1)
    expect(document.querySelectorAll('p')).toHaveLength(0)
    expect(document.querySelector('code').textContent).toBe('A\n\nB\n')
  })

  test('retains the existing preview link policies', () => {
    const markdown = '[Baserow](https://baserow.io)'
    const inert = new DOMParser().parseFromString(
      parseMarkdown(markdown),
      'text/html'
    )
    const clickable = new DOMParser().parseFromString(
      parseMarkdown(markdown, { openLinkOnClick: true }),
      'text/html'
    )

    expect(inert.querySelector('a').hasAttribute('href')).toBe(false)
    expect(clickable.querySelector('a').getAttribute('href')).toBe(
      'https://baserow.io'
    )
    expect(clickable.querySelector('a').getAttribute('target')).toBe('_blank')
    expect(clickable.querySelector('a').getAttribute('rel')).toBe(
      'noopener noreferrer nofollow'
    )
  })
})
