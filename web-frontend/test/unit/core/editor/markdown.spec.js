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

  const IMAGE_ATTRS = {
    src: 'https://example.com/img.png',
    alt: 'photo',
    title: null,
    userFileName: 'abc123_def456.png',
    maxWidth: '100%',
  }
  const listWithImage = (listType, text) => ({
    type: 'doc',
    content: [
      {
        type: listType,
        ...(listType === 'orderedList' ? { attrs: { start: 1 } } : {}),
        content: [
          {
            type: 'listItem',
            attrs: {},
            content: [
              {
                type: 'paragraph',
                content: [
                  ...(text ? [{ type: 'text', text }] : []),
                  { type: 'image', attrs: IMAGE_ATTRS },
                ],
              },
            ],
          },
        ],
      },
    ],
  })
  const findImage = (json) => {
    let found = null
    const walk = (node) => {
      if (node.type === 'image') found = found || node
      ;(node.content || []).forEach(walk)
    }
    walk(json)
    return found
  }

  test.each([
    ['ordered', 'orderedList', undefined, '1. '],
    ['bullet', 'bulletList', 'some text ', '- some text '],
  ])('keeps an image inside a %s list item', (_, listType, text, prefix) => {
    const opts = { enableImages: true }
    editor = createEditor(listWithImage(listType, text), opts)

    const reopened = reopen(editor, opts)
    editor = reopened.editor

    expect(reopened.markdown).toBe(
      `${prefix}![photo][abc123_def456.png](https://example.com/img.png)`
    )
    const listItem = editor.getJSON().content[0].content[0]
    expect(listItem.content).toHaveLength(1)
    expect(findImage(listItem).attrs).toMatchObject(IMAGE_ATTRS)
  })

  test('an image-only list item round-trips without &nbsp;', () => {
    const opts = { enableImages: true }
    editor = createEditor(listWithImage('orderedList'), opts)

    const reopened = reopen(editor, opts)
    editor = reopened.editor

    expect(reopened.markdown).not.toContain('&nbsp;')
    expect(JSON.stringify(editor.getJSON())).not.toContain('\\u00a0')
  })

  test('parses a stored list image with its user file name', () => {
    editor = new Editor({
      extensions: createRichTextEditorExtensions({ enableImages: true }),
      content: '1. ![photo][abc123_def456.jpg](https://example.com/img.png)',
      contentType: 'markdown',
    })

    const imageNode = findImage(editor.getJSON())
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

  test.each([
    [
      String.raw`[a \[x\] b](https://example.com)`,
      'a [x] b',
      String.raw`[a \[x\] b](https://example.com)`,
    ],
    [
      String.raw`[see \[1\] https://example.org](https://example.com)`,
      'see [1] https://example.org',
      String.raw`[see \[1\] https://example.org](https://example.com)`,
    ],
    [
      String.raw`[a \\\] b](https://example.com)`,
      'a \\] b',
      String.raw`[a \\\] b](https://example.com)`,
    ],
  ])(
    'keeps a link whose text has escaped brackets as one link: %s',
    (markdown, text, markdownOnSave) => {
      editor = createEditor(markdown)

      expect(editor.getJSON().content[0].content).toStrictEqual([
        {
          type: 'text',
          text,
          marks: [
            {
              type: 'link',
              attrs: expect.objectContaining({ href: 'https://example.com' }),
            },
          ],
        },
      ])
      expect(editor.getMarkdown()).toBe(markdownOnSave)
    }
  )

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
  test('shows a reference as its markdown when enableImages is false', () => {
    const document = new DOMParser().parseFromString(
      parseMarkdown('Hello ![img][abc123_def456.png]'),
      'text/html'
    )

    expect(document.body.textContent.trim()).toBe(
      'Hello ![img][abc123_def456.png]'
    )
    expect(document.querySelector('img, a, i')).toBeNull()
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

  test('leaves image sizing to the surface stylesheet', () => {
    const html = parseMarkdown(
      '![img][test_file.png](https://example.com/test.png)',
      { enableImages: true }
    )
    const image = new DOMParser()
      .parseFromString(html, 'text/html')
      .querySelector('img')

    expect(image).not.toBeNull()
    expect(image.hasAttribute('style')).toBe(false)
  })

  test('keeps the alt text of a resolved image', () => {
    const html = parseMarkdown(
      'before ![a *red* car][test_file.png](https://example.com/test.png)',
      { enableImages: true }
    )
    const image = new DOMParser()
      .parseFromString(html, 'text/html')
      .querySelector('img')

    expect(image.getAttribute('alt')).toBe('a red car')
  })
})

describe('parseMarkdown external image handling', () => {
  const parse = (markdown, enableImages) =>
    new DOMParser().parseFromString(
      parseMarkdown(markdown, { enableImages, openLinkOnClick: true }),
      'text/html'
    )

  // This preview is shown to anyone who can see a public view, so it never fetches a third-party URL.
  test('shows a plain https image as a placeholder when enableImages=true', () => {
    const document = parse(
      'see ![photo](https://example.com/photo.png) here',
      true
    )

    expect(document.querySelector('img')).toBeNull()
    expect(document.querySelector('a')).toBeNull()
    expect(
      document.querySelector('.rich-text-image-placeholder')
    ).not.toBeNull()
    expect(document.body.textContent).toContain('photo')
  })

  test.each([
    ['![photo](https://example.com/a((b)).png)'],
    ['![photo](https://example.com/a((b)).png "t")'],
  ])('never renders an img for an unresolved image %s', (markdown) => {
    const document = parse(`see ${markdown} here`, true)

    expect(document.querySelector('img')).toBeNull()
    expect(document.body.textContent).not.toContain('example.com')
    expect(document.body.textContent).toContain('photo')
  })

  test('shows a titled plain image as a placeholder', () => {
    const document = parse('![photo](https://example.com/a.png "t")', true)

    expect(document.querySelector('img')).toBeNull()
    expect(document.querySelector('a')).toBeNull()
  })

  test('shows a plain markdown image as its markdown when enableImages=false', () => {
    const document = parse(
      'see ![photo](https://example.com/photo.png) here',
      false
    )

    expect(document.body.textContent.trim()).toBe(
      'see ![photo](https://example.com/photo.png) here'
    )
    expect(document.querySelector('img, a, i')).toBeNull()
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

  test('drops a javascript: image entirely', () => {
    const html = parseMarkdown('![x](javascript:alert(1))', {
      enableImages: true,
      openLinkOnClick: true,
    })

    expect(html).not.toMatch(/<(img|a)\b/)
    expect(html).not.toContain('href=')
  })

  test('renders the Baserow ref as img and the external image as a placeholder', () => {
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
    expect(document.querySelector('a')).toBeNull()
    expect(document.body.textContent).toContain('ext')
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

  test.each([
    ['a relative path', '![logo](/media/logo.png)'],
    ['an uppercase https scheme', '![logo](HTTPS://example.com/logo.png)'],
    ['an uppercase http scheme', '![logo](HTTP://example.com/logo.png)'],
    ['a lowercase https scheme', '![logo](https://example.com/logo.png)'],
    ['a scheme relative path', '![logo](relative/path.png)'],
    ['an unsafe protocol', '![logo](javascript:alert(1))'],
  ])('keeps an image with %s unchanged on save', (_, markdown) => {
    editor = createEditor(markdown, { enableImages: true })

    const reopened = reopen(editor, { enableImages: true })
    editor = reopened.editor

    expect(reopened.markdown).toBe(markdown)
  })
})

describe('empty paragraph round trip with images', () => {
  const NAME = 'abc123_def456.png'
  const URL = 'https://storage.example.com/user_files/' + NAME

  // `prepareMarkdownForPreview` round trips the value through TipTap; the reference must survive it.
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

  test.each([['photo'], [String.raw`Screenshot \[1\]`]])(
    'keeps the link around the image %s through the round trip',
    (escapedAlt) => {
      const name = `${'a'.repeat(32)}_${'b'.repeat(64)}.png`
      const url = `https://example.com/media/user_files/${name}`
      const html = parseMarkdown(
        `[![${escapedAlt}][${name}](${url})](https://example.com)\n\n&nbsp;`,
        { enableImages: true, openLinkOnClick: true }
      )
      const document = new DOMParser().parseFromString(html, 'text/html')

      const img = document.querySelector('a img')
      expect(img).not.toBeNull()
      expect(img.getAttribute('src')).toBe(url)
      expect(img.closest('a').getAttribute('href')).toBe('https://example.com')
    }
  )

  // The backend reads a line starting with four backticks as a code fence and
  // returns what it holds as sent, but the round trip escapes those backticks
  // and brings the image out of code.
  const FENCED = '````![a][zzz_yyy.png](https://evil.example.com/x.png)```'

  test.each([
    ['blank lines before and after', `x\n\n\n\ny\n${FENCED}`],
    ['blank lines before', `x\n\n\n\n${FENCED}`],
    ['blank lines after', `${FENCED}\n\n\n\ny`],
    ['an empty paragraph', `&nbsp;\n\n${FENCED}`],
  ])(
    'never renders an image the round trip brings out of code (%s)',
    (_, markdown) => {
      const html = parseMarkdown(markdown, { enableImages: true })

      expect(html).not.toContain('<img')
      expect(html).not.toContain('evil.example.com')
    }
  )

  test('renders a resolved image next to blank lines', () => {
    const html = parseMarkdown(`x\n\n\n\n![photo][${NAME}](${URL})`, {
      enableImages: true,
    })

    expect(html).toContain('<img')
    expect(html).toContain(URL)
  })

  test('never renders an external image next to an empty paragraph', () => {
    const html = parseMarkdown('![x](https://example.com/x.png)\n\n&nbsp;', {
      enableImages: true,
    })

    expect(html).not.toContain('<img')
  })
})

describe('parseMarkdown with a non-string value', () => {
  // A rich text cell can still hold a value of the field's previous type
  // until the rows refetch after a field conversion.
  test.each([[42], [true], [[{ id: 1, value: 'row' }]], [{ id: 1 }]])(
    'renders %j as empty',
    (value) => {
      expect(parseMarkdown(value)).toBe('')
    }
  )
})

describe('image markdown without the image node', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  const IMAGE = '![c](https://example.com/c.png)'
  const REFERENCE = '![d][abc_d.png]'
  const REFERENCE_URL = 'https://example.com/media/user_files/abc_d.png'
  const RESOLVED_REFERENCE = `${REFERENCE}(${REFERENCE_URL})`

  const previewDocument = (markdown, options = {}) =>
    new DOMParser().parseFromString(
      parseMarkdown(markdown, options),
      'text/html'
    )

  const previewText = (markdown, options) =>
    previewDocument(markdown, options).body.textContent.trim()

  test('the editor shows an image as its markdown', () => {
    editor = createEditor(`see ${IMAGE} here`)

    expect(editor.state.doc.textContent).toBe(`see ${IMAGE} here`)
  })

  test('saving after an edit keeps the image markdown and its URL', () => {
    editor = createEditor(`see ${IMAGE}`)
    editor.commands.insertContentAt(
      editor.state.doc.content.size - 1,
      ' edited'
    )

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(editor.state.doc.textContent).toBe(`see ${IMAGE} edited`)
    expect(previewText(reopened.markdown)).toBe(`see ${IMAGE} edited`)
  })

  test('the editor keeps a linked image as linked markdown', () => {
    editor = createEditor(`[${IMAGE}](https://example.com)`)

    const [text] = editor.getJSON().content[0].content
    expect(text.text).toBe(IMAGE)
    expect(text.marks).toEqual([
      expect.objectContaining({
        type: 'link',
        attrs: expect.objectContaining({ href: 'https://example.com' }),
      }),
    ])
  })

  test('pastes image markdown as text', () => {
    editor = createEditor('')

    const slice = parseMarkdownClipboard(editor, `see ${IMAGE}`, false)

    expect(slice.content.textBetween(0, slice.content.size)).toBe(
      `see ${IMAGE}`
    )
  })

  test.each([
    ['full', '![photo][ref]', '[ref]: https://example.com/photo.png'],
    ['collapsed', '![photo][]', '[photo]: https://example.com/photo.png'],
    ['shortcut', '![photo]', '[photo]: https://example.com/photo.png'],
    [
      'title',
      '![photo][ref]',
      '[ref]: https://example.com/photo.png "Photo title"',
    ],
    [
      'escaped alt and title',
      String.raw`![a\]b][ref]`,
      String.raw`[ref]: https://example.com/photo.png "Photo \"title\""`,
    ],
    [
      'spaced destination',
      '![photo][ref]',
      '[ref]: <https://example.com/a b.png>',
    ],
  ])(
    'keeps a %s image reference destination through edit, copy and reopen',
    (name, reference, definition) => {
      const markdown = `Before\n\n${reference}\n\n${definition}`
      editor = createEditor(markdown)
      const originalText = editor.state.doc.textContent
      const destination =
        name === 'spaced destination'
          ? 'https://example.com/a%20b.png'
          : 'https://example.com/photo.png'

      expect(originalText).toContain(destination)
      expect(previewText(markdown)).toBe(`Before\n${originalText.slice(6)}`)
      const copied = serializeMarkdownClipboard(
        editor,
        editor.state.selection.$from.doc.slice(0)
      )
      expect(copied).toContain(destination)
      editor.commands.insertContentAt(7, ' edited')

      const reopened = reopen(editor)
      editor = reopened.editor
      expect(reopened.markdown).toContain(destination)
      expect(editor.state.doc.textContent).toBe(
        originalText.replace('Before', 'Before edited')
      )
      expect(previewText(reopened.markdown)).toContain(destination)
      expect(
        editor.getJSON().content.flatMap((node) => node.content ?? [])
      ).not.toContainEqual(expect.objectContaining({ type: 'image' }))
      if (name === 'title')
        expect(editor.state.doc.textContent).toContain('Photo title')
      if (name === 'escaped alt and title') {
        expect(editor.state.doc.textContent).toContain(String.raw`a\]b`)
        expect(editor.state.doc.textContent).toContain(
          String.raw`Photo \"title\"`
        )
      }
    }
  )

  test('keeps surrounding formatting and links sharing an image definition', () => {
    const url = 'https://example.com/photo.png'
    const markdown =
      `**![photo][ref]** [![photo][ref]](https://baserow.io) [source][ref]` +
      `\n\n[ref]: ${url} "Photo title"`
    editor = createEditor(markdown)
    const literal = `![photo](<${url}> "Photo title")`
    const preview = previewDocument(markdown, { openLinkOnClick: true })

    expect(preview.querySelector('strong').textContent).toBe(literal)
    expect(
      preview.querySelector('a[href="https://baserow.io"]').textContent
    ).toBe(literal)
    expect(preview.querySelector(`a[href="${url}"]`).textContent).toBe('source')
    expect(preview.querySelector('img')).toBeNull()
    editor.commands.insertContentAt(
      editor.state.doc.content.size - 1,
      ' edited'
    )

    const reopened = reopen(editor)
    editor = reopened.editor
    expect(editor.view.dom.querySelector('strong').textContent).toBe(literal)
    expect(
      editor.view.dom.querySelector('a[href="https://baserow.io"]').textContent
    ).toBe(literal)
    expect(editor.view.dom.querySelector(`a[href="${url}"]`).textContent).toBe(
      'source'
    )
    expect(editor.view.dom.querySelector('img')).toBeNull()
  })

  test.each([
    'javascript:alert(1)',
    'data:text/html,%3Cscript%3Ealert(1)%3C/script%3E',
  ])('keeps the unsafe image destination %s inert through saving', (url) => {
    const markdown = `![photo][ref]\n\n[ref]: ${url}`
    editor = createEditor(markdown)
    expect(editor.state.doc.textContent).toContain(url)
    expect(editor.view.dom.querySelector('img, a')).toBeNull()
    expect(previewDocument(markdown).querySelector('img, a')).toBeNull()
    editor.commands.insertContentAt(
      editor.state.doc.content.size - 1,
      ' edited'
    )

    const reopened = reopen(editor)
    editor = reopened.editor
    expect(reopened.markdown).toContain(url)
    expect(editor.state.doc.textContent).toContain(url)
    expect(editor.view.dom.querySelector('img, a')).toBeNull()
    expect(
      previewDocument(reopened.markdown).querySelector('img, a')
    ).toBeNull()
  })

  test('the editor shows a resolved reference as its text without the URL', () => {
    editor = createEditor(`see ${RESOLVED_REFERENCE}`)

    expect(editor.getJSON().content[0].content).toEqual([
      { type: 'text', text: `see ${REFERENCE}` },
    ])
  })

  test('saving a resolved reference after an edit drops its URL', () => {
    editor = createEditor(`see ${RESOLVED_REFERENCE}`)
    editor.commands.insertContentAt(
      editor.state.doc.content.size - 1,
      ' edited'
    )

    const reopened = reopen(editor)
    editor = reopened.editor

    expect(reopened.markdown).not.toContain(REFERENCE_URL)
    expect(editor.state.doc.textContent).toBe(`see ${REFERENCE} edited`)
    expect(previewText(reopened.markdown)).toBe(`see ${REFERENCE} edited`)
  })

  test('the preview shows a resolved reference as its text without the URL', () => {
    const document = previewDocument(`see ${RESOLVED_REFERENCE}`, {
      openLinkOnClick: true,
    })

    expect(document.body.textContent.trim()).toBe(`see ${REFERENCE}`)
    expect(document.querySelector('a')).toBeNull()
  })

  test('the preview keeps a linked image in its link', () => {
    const document = previewDocument(`[${IMAGE}](https://example.com)`, {
      openLinkOnClick: true,
    })

    const link = document.querySelector('a')
    expect(link.getAttribute('href')).toBe('https://example.com')
    expect(link.textContent).toBe(IMAGE)
  })

  test.each([
    [IMAGE],
    ['![c](https://example.com/c.png "title")'],
    ['![a](https://a.example/a.png)![b](https://b.example/b.png)'],
    ['![a ![b](https://b.example/b.png)](https://a.example/a.png)'],
    ['![a\\]b](https://example.com/c.png)'],
    ['\\![c](https://example.com/c.png)'],
    ['`![c](https://example.com/c.png)`'],
    ['![c](<https://example.com/a b.png>)'],
    ['![c][ref]\n\n[ref]: https://example.com/c.png'],
    ['![c][abc123_def456.png](https://example.com/c.png)'],
    ['![a\\]b][abc123_def456.png](https://example.com/c.png)'],
    ['![*a*][abc123_def456.png]'],
  ])('the editor and the preview show %s as the same text', (markdown) => {
    editor = createEditor(markdown)

    expect(previewText(markdown)).toBe(editor.state.doc.textContent)
  })
})

describe('escaped user file references', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  const LITERAL = '![photo][abc123_def456.png]'
  const ESCAPED_REFERENCE = String.raw`![photo]\[abc123_def456.png]`
  // The backend's former escape, still found in stored values.
  const LEGACY_ESCAPED_REFERENCE = String.raw`!\[photo][abc123_def456.png]`

  const hasImageNode = (instance) => {
    let found = false
    instance.state.doc.descendants((node) => {
      found = found || node.type.name === 'image'
    })
    return found
  }

  const render = (markdown, enableImages) => {
    editor = createEditor(markdown, { enableImages })
    const document = new DOMParser().parseFromString(
      parseMarkdown(markdown, { enableImages }),
      'text/html'
    )
    return {
      editorText: editor.state.doc.textContent,
      hasImageNode: hasImageNode(editor),
      previewText: document.body.textContent.trim(),
      previewElements: document.querySelectorAll('img, a, i').length,
    }
  }

  const literal = (text) => ({
    editorText: text,
    hasImageNode: false,
    previewText: text,
    previewElements: 0,
  })

  describe.each([[true], [false]])('with enableImages=%s', (enableImages) => {
    test.each([[ESCAPED_REFERENCE], [LEGACY_ESCAPED_REFERENCE]])(
      '%s shows as the literal reference',
      (escaped) => {
        expect(render(`see ${escaped} here`, enableImages)).toEqual(
          literal(`see ${LITERAL} here`)
        )
      }
    )

    test.each([[ESCAPED_REFERENCE], [LEGACY_ESCAPED_REFERENCE]])(
      'adjacent %s show as literal references',
      (escaped) => {
        expect(render(`${escaped}${escaped}`, enableImages)).toEqual(
          literal(`${LITERAL}${LITERAL}`)
        )
      }
    )

    // An alt may hold `\[`, so the legacy escape nested in one still reads as a reference.
    test('the escaped reference inside an image alt shows as literal text', () => {
      expect(render(`![foo ${ESCAPED_REFERENCE}`, enableImages)).toEqual(
        literal(`![foo ${LITERAL}`)
      )
    })
  })
})
