import { Editor } from '@tiptap/vue-3'

import { createRichTextEditorExtensions } from '@baserow/modules/core/editor/richTextExtensions'

function createEditor(content = '', enableImages = false) {
  return new Editor({
    content,
    contentType: typeof content === 'string' ? 'markdown' : 'json',
    extensions: createRichTextEditorExtensions({
      enableImages,
    }),
  })
}

function findImageNodes(editor) {
  const images = []
  editor.state.doc.descendants((node) => {
    if (node.type.name === 'image') {
      images.push(node)
    }
  })
  return images
}

describe('ScalableImage extension', () => {
  test('stores userFileName attribute on image node', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/resolved.png',
      alt: 'test',
      userFileName: 'abc123_def456.png',
    })

    const doc = editor.getJSON()
    const imageNode =
      doc.content.find((n) => n.content?.some((c) => c.type === 'image'))
        ?.content?.[0] || doc.content.find((n) => n.type === 'image')

    expect(imageNode).toBeDefined()
    expect(imageNode.attrs.userFileName).toBe('abc123_def456.png')
    expect(imageNode.attrs.src).toBe('https://example.com/resolved.png')

    editor.destroy()
  })

  test('serializes to markdown using userFileName with URL', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/resolved-url.png',
      alt: 'my image',
      userFileName: 'abc123_def456.png',
    })

    const markdown = editor.getMarkdown()

    expect(markdown).toContain(
      '![my image][abc123_def456.png](https://example.com/resolved-url.png)'
    )

    editor.destroy()
  })

  test('serializes an external image without userFileName as a markdown image', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/direct.png',
      alt: 'direct',
    })

    const markdown = editor.getMarkdown()

    expect(markdown).toContain('![direct](https://example.com/direct.png)')

    editor.destroy()
  })

  test('serializes a titled external image without userFileName as a titled image', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/direct.png',
      alt: 'direct',
      title: 'A title',
    })

    const markdown = editor.getMarkdown()

    expect(markdown).toContain(
      '![direct](https://example.com/direct.png "A title")'
    )

    editor.destroy()
  })

  test('maxWidth attribute renders in style', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'test.png',
      alt: 'test',
      maxWidth: '50%',
    })

    const html = editor.getHTML()

    expect(html).toContain('max-width: 50%')

    editor.destroy()
  })

  test('renders userFileName as a data attribute so HTML round-trips keep it', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/img.png',
      alt: 'test',
      userFileName: 'abc_hash123.png',
    })

    const html = editor.getHTML()

    expect(html).toContain('data-user-file-name="abc_hash123.png"')
    expect(html).not.toContain('userfilename=')
    expect(html).toContain('https://example.com/img.png')

    editor.destroy()
  })

  test('keeps userFileName through an HTML copy/paste round trip', () => {
    const source = createEditor('', true)
    source.commands.setImage({
      src: 'https://example.com/user_files/abc_def.png',
      alt: 'photo',
      userFileName: 'abc_def.png',
    })
    const html = source.getHTML()
    source.destroy()

    const target = createEditor('', true)
    target.commands.insertContent(html)

    const images = findImageNodes(target)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.userFileName).toBe('abc_def.png')
    expect(target.getMarkdown()).toContain(
      '![photo][abc_def.png](https://example.com/user_files/abc_def.png)'
    )

    target.destroy()
  })
})

describe('ScalableImage markdown parsing', () => {
  test('parses a Baserow image ref with URL into an image node', () => {
    const editor = createEditor(
      'before ![photo][abc_def.png](https://example.com/user_files/abc_def.png) after',
      true
    )

    const images = findImageNodes(editor)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.src).toBe(
      'https://example.com/user_files/abc_def.png'
    )
    expect(images[0].attrs.alt).toBe('photo')
    expect(images[0].attrs.userFileName).toBe('abc_def.png')
    expect(editor.getMarkdown()).toContain(
      '![photo][abc_def.png](https://example.com/user_files/abc_def.png)'
    )

    editor.destroy()
  })

  test('round-trips escaped brackets in the alt text', () => {
    const markdown = String.raw`![my\]pic][abc_def.png](https://example.com/f.png)`
    const editor = createEditor(markdown, true)

    const images = findImageNodes(editor)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.alt).toBe('my]pic')
    expect(editor.getMarkdown()).toBe(markdown)

    editor.destroy()
  })

  test('creates an image node for a plain https markdown image', () => {
    const editor = createEditor(
      'see ![photo](https://example.com/user_files/abc_def.png) here',
      true
    )

    const images = findImageNodes(editor)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.src).toBe(
      'https://example.com/user_files/abc_def.png'
    )
    expect(images[0].attrs.alt).toBe('photo')
    expect(images[0].attrs.userFileName).toBeNull()

    editor.destroy()
  })

  test.each([['javascript:alert(1)'], ['data:image/png;base64,AAAA']])(
    'renders a plain image with unsafe url %s as text only',
    (url) => {
      const editor = createEditor(`![x](${url})`, true)

      expect(findImageNodes(editor)).toHaveLength(0)
      const html = editor.getHTML()
      expect(html).not.toContain('<img')
      expect(html).not.toContain('<a')
      expect(html).toContain('x')

      editor.destroy()
    }
  )

  test('rejects user file names containing path separators', () => {
    const editor = createEditor(
      '![x][abc_def.png/../evil.png](https://example.com/evil.png)',
      true
    )

    expect(findImageNodes(editor)).toHaveLength(0)
    expect(editor.getHTML()).not.toContain('<img')

    editor.destroy()
  })

  test('does not parse images when enableImages is false', () => {
    const editor = createEditor(
      '![photo][abc_def.png](https://example.com/f.png)',
      false
    )

    expect(findImageNodes(editor)).toHaveLength(0)

    editor.destroy()
  })
})

describe('ScalableImage HTML parsing', () => {
  test('accepts pasted <img> with https src even without data-user-file-name', () => {
    const editor = createEditor('', true)
    editor.commands.insertContent(
      '<p>a</p><img src="https://example.com/photo.png" alt="x"><p>b</p>'
    )

    const images = findImageNodes(editor)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.src).toBe('https://example.com/photo.png')
    expect(images[0].attrs.userFileName).toBeNull()

    editor.destroy()
  })

  test('rejects pasted <img> with unsafe src without data-user-file-name', () => {
    const editor = createEditor('', true)
    editor.commands.insertContent(
      '<p>a</p><img src="javascript:alert(1)" alt="x"><p>b</p>'
    )

    expect(findImageNodes(editor)).toHaveLength(0)

    editor.destroy()
  })

  test('parses <img> with data-user-file-name into an image node', () => {
    const editor = createEditor('', true)
    editor.commands.insertContent(
      '<img src="https://example.com/f.png" alt="x" data-user-file-name="abc_def.png">'
    )

    const images = findImageNodes(editor)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.userFileName).toBe('abc_def.png')
    expect(images[0].attrs.src).toBe('https://example.com/f.png')

    editor.destroy()
  })
})
