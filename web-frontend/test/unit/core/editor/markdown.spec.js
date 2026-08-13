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

function createEditor(
  content,
  { users = null, enableImages = false, contentType = null } = {}
) {
  const extensions = createRichTextEditorExtensions({ enableImages })
  if (users !== null) {
    extensions.push(createMention({ users }))
  }
  return new Editor({
    extensions,
    content,
    contentType:
      contentType ?? (typeof content === 'string' ? 'markdown' : 'json'),
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

  test('preserves multiple empty paragraphs at both document boundaries', () => {
    const document = {
      type: 'doc',
      content: [
        paragraph(),
        paragraph(),
        paragraph('A'),
        paragraph(),
        paragraph(),
      ],
    }
    editor = createEditor(document)

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(reopened.markdown).toBe('&nbsp;\n\n&nbsp;\n\nA\n\n\n\n&nbsp;')
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

  test('preserves the marker style of a lettered ordered list', () => {
    editor = createEditor(
      '<ol type="a"><li><p>one</p></li><li><p>two</p></li></ol>',
      { contentType: 'html' }
    )

    expect(editor.getJSON().content[0].attrs.type).toBe('a')
    expect(editor.getMarkdown()).toBe('a. one\nb. two')
  })

  test('preserves the marker style of a roman ordered list', () => {
    editor = createEditor(
      '<ol type="I"><li><p>one</p></li><li><p>two</p></li></ol>',
      { contentType: 'html' }
    )

    expect(editor.getMarkdown()).toBe('I. one\nII. two')
  })

  test('preserves the marker style of a lettered list with a start offset', () => {
    editor = createEditor(
      '<ol start="3" type="a"><li><p>one</p></li><li><p>two</p></li></ol>',
      { contentType: 'html' }
    )

    expect(editor.getMarkdown()).toBe('c. one\nd. two')
  })

  test('does not turn raw Markdown HTML into editor DOM', () => {
    editor = createEditor('<script>alert("unsafe")</script>')

    expect(editor.getHTML()).not.toContain('<script>')
  })

  test('preserves an image inside an ordered list item', () => {
    const document = {
      type: 'doc',
      content: [
        {
          type: 'orderedList',
          attrs: { start: 1 },
          content: [
            {
              type: 'listItem',
              attrs: {},
              content: [
                paragraph(),
                {
                  type: 'image',
                  attrs: {
                    src: 'https://example.com/img.png',
                    alt: 'photo',
                    title: null,
                    userFileName: 'abc123_def456.png',
                    maxWidth: '100%',
                  },
                },
              ],
            },
          ],
        },
      ],
    }
    const opts = { enableImages: true }
    editor = createEditor(document, opts)

    const reopened = reopen(editor, opts)
    editor = reopened.editor

    const json = editor.getJSON()
    const listItem = json.content[0].content[0]
    const imageNode = listItem.content.find((n) => n.type === 'image')
    expect(imageNode).toBeTruthy()
    expect(imageNode.attrs.src).toBe('https://example.com/img.png')
    expect(imageNode.attrs.alt).toBe('photo')

    const firstPara = listItem.content[0]
    expect(firstPara.type).toBe('paragraph')
    expect(firstPara.content).toBeUndefined()
  })

  test('does not show &nbsp; text in list items after round-trip', () => {
    const document = {
      type: 'doc',
      content: [
        {
          type: 'orderedList',
          attrs: { start: 1 },
          content: [
            {
              type: 'listItem',
              attrs: {},
              content: [
                paragraph(),
                {
                  type: 'image',
                  attrs: {
                    src: 'https://example.com/img.png',
                    alt: 'photo',
                    title: null,
                    userFileName: 'abc123_def456.png',
                    maxWidth: '100%',
                  },
                },
              ],
            },
          ],
        },
      ],
    }
    const opts = { enableImages: true }
    editor = createEditor(document, opts)
    const markdown = editor.getMarkdown()
    expect(markdown).toContain('&nbsp;')

    const reopened = reopen(editor, opts)
    editor = reopened.editor
    const json = editor.getJSON()
    const allText = JSON.stringify(json)
    expect(allText).not.toContain('&nbsp;')
    expect(allText).not.toContain('\\u00a0')
  })

  test('preserves an image inside a bullet list item', () => {
    const document = {
      type: 'doc',
      content: [
        {
          type: 'bulletList',
          content: [
            {
              type: 'listItem',
              attrs: {},
              content: [
                paragraph('some text'),
                {
                  type: 'image',
                  attrs: {
                    src: 'https://example.com/img.png',
                    alt: 'photo',
                    title: null,
                    userFileName: 'abc123_def456.png',
                    maxWidth: '100%',
                  },
                },
              ],
            },
          ],
        },
      ],
    }
    const opts = { enableImages: true }
    editor = createEditor(document, opts)

    const reopened = reopen(editor, opts)
    editor = reopened.editor

    const json = editor.getJSON()
    const listItem = json.content[0].content[0]
    const imageNode = listItem.content.find((n) => n.type === 'image')
    expect(imageNode).toBeTruthy()
    expect(imageNode.attrs.src).toBe('https://example.com/img.png')
  })

  test('preserves image with userFileName through full app flow', () => {
    const imageAttrs = {
      src: 'https://example.com/img.png',
      alt: 'photo',
      title: null,
      userFileName: 'abc123_def456.jpg',
      maxWidth: '100%',
    }
    editor = createEditor(
      {
        type: 'doc',
        content: [
          {
            type: 'orderedList',
            attrs: { start: 1 },
            content: [
              {
                type: 'listItem',
                attrs: {},
                content: [paragraph(), { type: 'image', attrs: imageAttrs }],
              },
            ],
          },
        ],
      },
      { enableImages: true }
    )

    const markdown = editor.getMarkdown()
    expect(markdown).toContain('[abc123_def456.jpg]')
    expect(markdown).toContain('https://example.com/img.png')
    editor.destroy()

    // The stored markdown (as returned by the backend with resolved URLs) is
    // parsed directly, the image tokenizer stamps userFileName itself.
    editor = new Editor({
      extensions: createRichTextEditorExtensions({ enableImages: true }),
      content: markdown,
      contentType: 'markdown',
    })

    const json = editor.getJSON()
    const listItem = json.content[0].content[0]
    const imageNode = listItem.content.find((n) => n.type === 'image')
    expect(imageNode).toBeTruthy()
    expect(imageNode.attrs.src).toBe('https://example.com/img.png')
    expect(imageNode.attrs.userFileName).toBe('abc123_def456.jpg')
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

  test('does not parse mention IDs embedded in email-like text', () => {
    const users = [{ user_id: 1, name: 'Jane Doe' }]
    editor = createEditor('email@1.example and @1', { users })
    const container = document.createElement('div')
    container.innerHTML = editor.getHTML()

    const mentions = container.querySelectorAll('[data-type="mention"]')
    expect(mentions).toHaveLength(1)
    expect(mentions[0].textContent).toBe('@Jane Doe')
    expect(container.textContent).toBe('email@1.example and @Jane Doe')
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

  test('renders the boundary empty paragraph sentinel as an empty line', () => {
    const html = parseMarkdown('&nbsp;\n\nA')
    const document = new DOMParser().parseFromString(html, 'text/html')
    const paragraphs = [...document.querySelectorAll('p')]

    expect(paragraphs).toHaveLength(2)
    expect(paragraphs.map((element) => element.textContent)).toStrictEqual([
      '\u00a0',
      'A',
    ])
  })

  test('renders plain paragraphs without empty-line placeholders', () => {
    const html = parseMarkdown('A\n\nB')

    expect(html).not.toContain('&nbsp;')
    expect(html).not.toContain('\u00a0')
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

describe('parseMarkdown image handling', () => {
  test('replaces images with placeholder when enableImages is false', () => {
    const html = parseMarkdown(
      'Hello ![img][abc123_def456.png](https://example.com/file.png)'
    )

    // `<img` excludes a real image; the `<i` icon element is not one. The alt
    // text is asserted on its own so it cannot be satisfied by the class name.
    expect(html).not.toContain('<img')
    expect(html).toContain('Hello')
    expect(html).toContain('iconoir-media-image')
    expect(html).toMatch(/<\/i>\s*img/)
  })

  test('renders images with inline URLs when enableImages is true', () => {
    const html = parseMarkdown(
      '![alt text][abc123_def456.png](https://example.com/user_files/abc123_def456.png)',
      { enableImages: true }
    )

    expect(html).toContain('<img')
    expect(html).toContain(
      'src="https://example.com/user_files/abc123_def456.png"'
    )
  })

  test('renders content without image refs unchanged', () => {
    const html = parseMarkdown('Plain text without images', {
      enableImages: true,
    })

    expect(html).not.toContain('<img')
    expect(html).toContain('Plain text without images')
  })

  test('handles multiple images', () => {
    const content = [
      '![a][file1_hash1.png](https://cdn.example.com/file1.png)',
      '',
      '![b][file2_hash2.jpg](https://cdn.example.com/file2.jpg)',
    ].join('\n')
    const html = parseMarkdown(content, { enableImages: true })

    expect(html).toContain('src="https://cdn.example.com/file1.png"')
    expect(html).toContain('src="https://cdn.example.com/file2.jpg"')
  })

  test('applies max-width style to images', () => {
    const html = parseMarkdown(
      '![img][test_file.png](https://example.com/test.png)',
      { enableImages: true }
    )

    expect(html).toContain('max-width: 100%')
  })
})

describe('parseMarkdown external image handling', () => {
  const parse = (markdown, enableImages) =>
    new DOMParser().parseFromString(
      parseMarkdown(markdown, { enableImages, openLinkOnClick: true }),
      'text/html'
    )

  // External images are not supported in either mode: this preview is shown to
  // anyone who can see a public view, so it must never fetch a third-party URL.
  test('renders a plain https markdown image as a link when enableImages=true', () => {
    const document = parse(
      'see ![photo](https://example.com/photo.png) here',
      true
    )

    expect(document.querySelector('img')).toBeNull()
    const link = document.querySelector('a')
    expect(link).not.toBeNull()
    expect(link.getAttribute('href')).toBe('https://example.com/photo.png')
  })

  test('renders a plain markdown image as a link when enableImages=false', () => {
    const html = parseMarkdown(
      'see ![photo](https://example.com/photo.png) here',
      { enableImages: false }
    )

    expect(html).not.toContain('<img')
    expect(html).toContain('photo')
  })

  test.each([
    ['![x](data:image/png;base64,AAAA)'],
    ['![x](javascript:alert(1))'],
  ])('never renders an img for %s', (markdown) => {
    for (const enableImages of [true, false]) {
      const html = parseMarkdown(markdown, {
        enableImages,
        openLinkOnClick: true,
      })
      expect(html).not.toContain('<img')
      expect(html).toContain('x')
    }
  })

  // The demotion is unconditional now, so an unsafe scheme is no longer
  // filtered by a scheme check before it reaches the renderer. It must still
  // never produce a live href in any mode.
  test.each([
    '![x](javascript:alert(1))',
    '![x](data:text/html;base64,PHNjcmlwdD4=)',
    '![x](vbscript:msgbox(1))',
    '![x](https://ok.com/a.png)',
  ])('%s yields no img and no live href in any mode', (markdown) => {
    for (const enableImages of [true, false]) {
      for (const openLinkOnClick of [true, false]) {
        const html = parseMarkdown(markdown, { enableImages, openLinkOnClick })
        expect(html).not.toContain('<img')
        expect(html).not.toMatch(/href\s*=\s*"\s*(javascript|data|vbscript):/i)
      }
    }
  })

  test('drops a javascript: href entirely when downgrading an image', () => {
    const html = parseMarkdown('![x](javascript:alert(1))', {
      enableImages: true,
      openLinkOnClick: true,
    })

    expect(html).not.toMatch(/<(img|a)\b/)
    expect(html).not.toContain('href=')
  })

  test('renders the Baserow ref as img and the external image as a link', () => {
    const document = parse(
      [
        '![photo][abc123_def456.png](https://example.com/user_files/abc123_def456.png)',
        '',
        '![ext](https://example.com/external.png)',
      ].join('\n'),
      true
    )

    const images = [...document.querySelectorAll('img')]
    expect(images).toHaveLength(1)
    expect(images[0].getAttribute('src')).toBe(
      'https://example.com/user_files/abc123_def456.png'
    )
    const link = document.querySelector('a')
    expect(link.getAttribute('href')).toBe('https://example.com/external.png')
  })

  test('renders external image as a link, never an img', () => {
    const document = parse('![photo](https://example.com/photo.png)', true)

    expect(document.querySelector('img')).toBeNull()
    expect(document.querySelector('a').getAttribute('href')).toBe(
      'https://example.com/photo.png'
    )
  })

  test('renders a Baserow ref with a path separator in the name as text', () => {
    const html = parseMarkdown(
      '![x][abc_def.png/../evil.png](https://evil.com/e.png)',
      { enableImages: true }
    )

    expect(html).not.toContain('<img')
  })
})

describe('external image round trips', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  // Rich text images are Baserow user files only, so every plain image is
  // demoted regardless of scheme or case. Stored values written before this
  // rule are demoted on the next save rather than kept as images.
  test.each([
    ['a relative path', '![logo](/media/logo.png)'],
    ['an uppercase https scheme', '![logo](HTTPS://example.com/logo.png)'],
    ['an uppercase http scheme', '![logo](HTTP://example.com/logo.png)'],
    ['a lowercase https scheme', '![logo](https://example.com/logo.png)'],
    ['a scheme relative path', '![logo](relative/path.png)'],
    ['an unsafe protocol', '![logo](javascript:alert(1))'],
  ])('demotes an image with %s on save', (_, markdown) => {
    editor = createEditor(markdown, { enableImages: true })

    const reopened = reopen(editor, { enableImages: true })
    editor = reopened.editor

    expect(reopened.markdown).not.toContain('![logo]')
    expect(reopened.markdown).toContain('logo')
  })
})

describe('empty paragraph round trip with images', () => {
  const NAME = 'abc123_def456.png'
  const URL = 'https://storage.example.com/user_files/' + NAME

  // `prepareMarkdownForPreview` round trips a value through TipTap to make
  // empty paragraphs visible. It has to see the reference as stored: once
  // `preprocessRichTextImages` has rewritten it to a plain `![alt](url)`, the
  // round trip's own parse demotes it to a link, because a plain image is not
  // a user file reference.
  test('renders an image whose cell also contains an empty paragraph', () => {
    const html = parseMarkdown(`![photo][${NAME}](${URL})\n\n&nbsp;`, {
      enableImages: true,
    })

    expect(html).toContain('<img')
    expect(html).toContain(URL)
  })

  test('renders an image with no trailing empty paragraph', () => {
    const html = parseMarkdown(`![photo][${NAME}](${URL})`, {
      enableImages: true,
    })

    expect(html).toContain('<img')
  })

  // The round trip must not resurrect an external image the demotion removed.
  test('keeps an external image demoted next to an empty paragraph', () => {
    const html = parseMarkdown('![x](https://example.com/x.png)\n\n&nbsp;', {
      enableImages: true,
    })

    expect(html).not.toContain('<img')
  })
})
