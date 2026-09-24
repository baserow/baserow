import { Editor } from '@tiptap/vue-3'

import { createRichTextEditorExtensions } from '@baserow/modules/core/editor/richTextExtensions'
import {
  clearTrustedImageUrls,
  registerTrustedImageUrl,
} from '@baserow/modules/core/editor/trustedImageUrls'

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

afterEach(() => {
  clearTrustedImageUrls()
})

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
    registerTrustedImageUrl('https://example.com/img.png')
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
    registerTrustedImageUrl('https://example.com/user_files/abc_def.png')
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

  test.each([
    ['https://example.com/p.png'],
    ['javascript:alert(1)'],
    ['data:image/png;base64,AAAA'],
  ])('keeps the external image %s as a placeholder node', (url) => {
    const markdown = `![photo](${url})`
    const editor = createEditor(markdown, true)

    const images = findImageNodes(editor)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.userFileName).toBeNull()
    expect(editor.view.dom.querySelector('img')).toBeNull()
    expect(editor.view.dom.querySelector('a')).toBeNull()
    expect(editor.getMarkdown()).toBe(markdown)

    editor.destroy()
  })

  test('keeps the title of an external image', () => {
    const markdown = '![photo](https://example.com/p.png "t")'
    const editor = createEditor(markdown, true)

    expect(editor.getMarkdown()).toBe(markdown)

    editor.destroy()
  })

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
  // Pasted HTML is the other way an external image could enter the document.
  test('rejects pasted <img> with https src without data-user-file-name', () => {
    const editor = createEditor('', true)
    editor.commands.insertContent(
      '<p>a</p><img src="https://example.com/photo.png" alt="x"><p>b</p>'
    )

    expect(findImageNodes(editor)).toHaveLength(0)

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

describe('ScalableImage only loads trusted URLs', () => {
  test('pasted HTML with a user file name and a foreign src renders a placeholder', () => {
    const editor = createEditor('', true)
    editor.commands.insertContent(
      '<img src="https://evil.example.com/pixel.png" alt="x" data-user-file-name="abc_def.png">'
    )

    const images = findImageNodes(editor)
    expect(images).toHaveLength(1)
    expect(images[0].attrs.userFileName).toBe('abc_def.png')
    expect(editor.view.dom.querySelector('img')).toBeNull()
    const placeholder = editor.view.dom.querySelector(
      '.rich-text-editor__image-placeholder'
    )
    expect(placeholder).not.toBeNull()
    expect(placeholder.getAttribute('data-user-file-name')).toBe('abc_def.png')
    expect(editor.getHTML()).not.toContain('evil.example.com')
    // The reference is kept, so the backend resolves it on save.
    expect(editor.getMarkdown()).toContain('![x][abc_def.png]')

    editor.destroy()
  })

  test('a registered src renders an img', () => {
    registerTrustedImageUrl(
      'https://baserow.example.com/user_files/abc_def.png'
    )
    const editor = createEditor(
      '![x][abc_def.png](https://baserow.example.com/user_files/abc_def.png)',
      true
    )

    const img = editor.view.dom.querySelector('img')
    expect(img).not.toBeNull()
    expect(img.getAttribute('src')).toBe(
      'https://baserow.example.com/user_files/abc_def.png'
    )

    editor.destroy()
  })

  test('a Markdown reference with an unregistered URL renders a placeholder', () => {
    const editor = createEditor(
      '![x][abc_def.png](https://evil.example.com/pixel.png)',
      true
    )

    expect(findImageNodes(editor)).toHaveLength(1)
    expect(editor.view.dom.querySelector('img')).toBeNull()

    editor.destroy()
  })

  test.each([['https://example.com/a.png'], ['javascript:alert(1)']])(
    'typing ![x](%s) creates the same placeholder node',
    (url) => {
      const editor = createEditor('', true)
      editor.commands.insertContent(`![x](${url}`)
      const { from, to } = editor.state.selection
      const handled = editor.view.someProp('handleTextInput', (handler) =>
        handler(editor.view, from, to, ')')
      )

      expect(handled).toBe(true)
      expect(findImageNodes(editor)).toHaveLength(1)
      expect(editor.view.dom.querySelector('img')).toBeNull()
      expect(editor.getMarkdown()).toContain(`![x](${url})`)

      editor.destroy()
    }
  )

  test('an external image survives an in-editor copy/paste', () => {
    const markdown = '![x](https://example.com/a.png)'
    const source = createEditor(markdown, true)
    const target = createEditor('', true)

    target.commands.insertContent(source.getHTML())

    expect(findImageNodes(target)).toHaveLength(1)
    expect(target.getMarkdown()).toBe(markdown)

    source.destroy()
    target.destroy()
  })
})
