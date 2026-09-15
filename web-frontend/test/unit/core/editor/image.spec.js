import { Editor } from '@tiptap/vue-3'

import { createRichTextEditorExtensions } from '@baserow/modules/core/editor/richTextExtensions'
import { preprocessRichTextImages } from '@baserow/modules/core/editor/richTextImageUtils'

function createEditor(content = '', enableImages = false) {
  return new Editor({
    content,
    contentType: typeof content === 'string' ? 'markdown' : 'json',
    extensions: createRichTextEditorExtensions({
      enableImages,
    }),
  })
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

  test('falls back to standard markdown when userFileName is null', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/direct.png',
      alt: 'direct',
    })

    const markdown = editor.getMarkdown()

    expect(markdown).toContain('![direct](https://example.com/direct.png)')
    expect(markdown).not.toContain('][')

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

  test('userFileName is not rendered to DOM', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/img.png',
      alt: 'test',
      userFileName: 'secret_hash123.png',
    })

    const html = editor.getHTML()

    expect(html).not.toContain('secret_hash123.png')
    expect(html).toContain('https://example.com/img.png')

    editor.destroy()
  })
})

describe('applyNameMap round-trip', () => {
  test('sets userFileName on image nodes via transaction', () => {
    const editor = createEditor('', true)
    editor.commands.setImage({
      src: 'https://example.com/file.png',
      alt: 'test',
    })

    let found = false
    editor.state.doc.descendants((node) => {
      if (node.type.name === 'image') {
        expect(node.attrs.userFileName).toBeNull()
        found = true
      }
    })
    expect(found).toBe(true)

    const nameMap = { 'https://example.com/file.png': 'abc_def.png' }
    const { tr } = editor.state
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'image' && node.attrs.src) {
        const name = nameMap[node.attrs.src]
        if (name) {
          tr.setNodeMarkup(pos, undefined, {
            ...node.attrs,
            userFileName: name,
          })
        }
      }
    })
    editor.view.dispatch(tr)

    editor.state.doc.descendants((node) => {
      if (node.type.name === 'image') {
        expect(node.attrs.userFileName).toBe('abc_def.png')
      }
    })

    expect(editor.getMarkdown()).toContain(
      '![test][abc_def.png](https://example.com/file.png)'
    )

    editor.destroy()
  })

  test('standard markdown image is parsed as image node with enableImages', () => {
    const standardMd = '![photo](https://example.com/user_files/abc_def.png)'
    const editor = createEditor(standardMd, true)

    let imageFound = false
    editor.state.doc.descendants((node) => {
      if (node.type.name === 'image') {
        expect(node.attrs.src).toBe(
          'https://example.com/user_files/abc_def.png'
        )
        expect(node.attrs.alt).toBe('photo')
        imageFound = true
      }
    })
    expect(imageFound).toBe(true)

    editor.destroy()
  })

  test('preprocessRichTextImages + applyNameMap produces correct image node', () => {
    const apiContent =
      '![photo][abc_def.png](https://example.com/user_files/abc_def.png)'

    const { content, nameMap } = preprocessRichTextImages(apiContent)
    expect(content).toBe('![photo](https://example.com/user_files/abc_def.png)')
    expect(nameMap).toEqual({
      'https://example.com/user_files/abc_def.png': 'abc_def.png',
    })

    const editor = createEditor(content, true)

    const { tr } = editor.state
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'image' && node.attrs.src) {
        const name = nameMap[node.attrs.src]
        if (name && node.attrs.userFileName !== name) {
          tr.setNodeMarkup(pos, undefined, {
            ...node.attrs,
            userFileName: name,
          })
        }
      }
    })
    editor.view.dispatch(tr)

    const savedMarkdown = editor.getMarkdown()
    expect(savedMarkdown).toContain(
      '![photo][abc_def.png](https://example.com/user_files/abc_def.png)'
    )

    editor.destroy()
  })
})
