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

  test('never renders an external image next to an empty paragraph', () => {
    const html = parseMarkdown('![x](https://example.com/x.png)\n\n&nbsp;', {
      enableImages: true,
    })

    expect(html).not.toContain('<img')
  })
})
