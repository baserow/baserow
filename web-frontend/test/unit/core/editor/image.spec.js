import { Editor } from '@tiptap/vue-3'
import { closeHistory } from '@tiptap/pm/history'

import { createRichTextEditorExtensions } from '@baserow/modules/core/editor/richTextExtensions'
import {
  findPendingImages,
  insertPendingImages,
  withoutPendingImages,
} from '@baserow/modules/core/editor/image'
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

describe('Linked images', () => {
  const NAME = `${'a'.repeat(32)}_${'b'.repeat(64)}.png`
  const URL = `https://example.com/media/user_files/${NAME}`
  const LINK = 'https://example.com'
  const BADGE = `[![badge](https://img.shields.io/x.svg)](${LINK})`
  const LINK_MARK = {
    type: 'link',
    attrs: expect.objectContaining({ href: LINK }),
  }

  const imageJSON = (editor) =>
    findImageNodes(editor).map((node) => node.toJSON())

  const wordsJSON = (editor) => {
    const words = []
    editor.state.doc.descendants((node) => {
      if (node.isText && node.text.trim()) {
        words.push(node.toJSON())
      }
    })
    return words
  }

  test.each([
    ['a Baserow reference', `[![alt][${NAME}](${URL})](${LINK})`],
    ['an unresolved Baserow reference', `[![alt][${NAME}]](${LINK})`],
    ['a titled link', `[![alt][${NAME}](${URL})](${LINK} "Home")`],
    ['an external badge', BADGE],
    [
      'an alt with escaped brackets',
      String.raw`[![Screenshot \[1\]][${NAME}](${URL})](${LINK})`,
    ],
    [
      'an alt ending in a backslash',
      String.raw`[![shot\\][${NAME}](${URL})](${LINK})`,
    ],
    [
      'an external badge with escaped brackets',
      String.raw`[![build \[main\]](https://img.shields.io/x.svg)](${LINK})`,
    ],
  ])('keeps the link of %s on the image and on save', (_, markdown) => {
    const editor = createEditor(markdown, true)

    const images = imageJSON(editor)
    expect(images).toHaveLength(1)
    expect(images[0].marks).toEqual([LINK_MARK])
    expect(editor.getMarkdown()).toBe(markdown)

    editor.destroy()
  })

  test.each([
    ['brackets', 'Screenshot [1]', String.raw`Screenshot \[1\]`],
    ['a trailing backslash', 'shot\\', String.raw`shot\\`],
  ])(
    'reopens an image linked in the editor whose alt has %s, with the rest of the cell',
    (_, alt, escapedAlt) => {
      const otherName = `${'c'.repeat(32)}_${'d'.repeat(64)}.png`
      const otherImage = `![other][${otherName}](https://example.com/media/user_files/${otherName})`
      const editor = createEditor(
        `# Title\n\n**bold** ${otherImage}\n\nlast ![${escapedAlt}][${NAME}](${URL})`,
        true
      )
      let imagePos = null
      editor.state.doc.descendants((node, pos) => {
        if (node.attrs.userFileName === NAME) {
          imagePos = pos
        }
      })
      editor.chain().setNodeSelection(imagePos).setLink({ href: LINK }).run()
      const markdownOnSave = editor.getMarkdown()
      editor.destroy()

      const reopened = createEditor(markdownOnSave, true)

      expect(markdownOnSave).toBe(
        `# Title\n\n**bold** ${otherImage}\n\nlast [![${escapedAlt}][${NAME}](${URL})](${LINK})`
      )
      expect(imageJSON(reopened)).toEqual([
        expect.objectContaining({
          attrs: expect.objectContaining({ userFileName: otherName }),
        }),
        expect.objectContaining({
          attrs: expect.objectContaining({ alt, userFileName: NAME }),
          marks: [LINK_MARK],
        }),
      ])
      expect(reopened.getMarkdown()).toBe(markdownOnSave)

      reopened.destroy()
    }
  )

  test('renders a resolved linked image as an img inside the link', () => {
    registerTrustedImageUrl(URL)
    const editor = createEditor(`[![alt][${NAME}](${URL})](${LINK})`, true)

    const img = editor.view.dom.querySelector('a img')
    expect(img).not.toBeNull()
    expect(img.closest('a').getAttribute('href')).toBe(LINK)

    editor.destroy()
  })

  test('renders an external badge as a placeholder inside the link', () => {
    const editor = createEditor(BADGE, true)

    expect(editor.view.dom.querySelector('img')).toBeNull()
    const placeholder = editor.view.dom.querySelector(
      'a .rich-text-editor__image-placeholder'
    )
    expect(placeholder).not.toBeNull()
    expect(placeholder.closest('a').getAttribute('href')).toBe(LINK)

    editor.destroy()
  })

  // One link around text and an image saves as one link per piece, with the spaces between unlinked.
  test.each([
    ['in the middle', `[see ![alt][${NAME}](${URL}) here](${LINK})`],
    ['at the end', `[see ![alt][${NAME}](${URL})](${LINK})`],
    ['at the start', `[![alt][${NAME}](${URL}) here](${LINK})`],
    ['with no spaces', `[see![alt][${NAME}](${URL})here](${LINK})`],
  ])(
    'keeps the link of text and an image linked together %s',
    (_, markdown) => {
      const editor = createEditor(markdown, true)
      const markdownOnSave = editor.getMarkdown()
      editor.destroy()

      const reopened = createEditor(markdownOnSave, true)

      expect(imageJSON(reopened)[0].marks).toEqual([LINK_MARK])
      wordsJSON(reopened).forEach((word) =>
        expect(word.marks).toEqual([LINK_MARK])
      )
      expect(reopened.getMarkdown()).toBe(markdownOnSave)

      reopened.destroy()
    }
  )

  test('saves the space between two images under one link without an empty link', () => {
    const otherName = `${'c'.repeat(32)}_${'d'.repeat(64)}.png`
    const otherUrl = `https://example.com/media/user_files/${otherName}`
    const editor = createEditor(
      `[![a][${NAME}](${URL}) ![b][${otherName}](${otherUrl})](${LINK})`,
      true
    )
    const markdownOnSave = editor.getMarkdown()
    editor.destroy()

    const reopened = createEditor(markdownOnSave, true)

    expect(markdownOnSave).toBe(
      `[![a][${NAME}](${URL})](${LINK}) [![b][${otherName}](${otherUrl})](${LINK})`
    )
    expect(imageJSON(reopened).map(({ marks }) => marks)).toEqual([
      [LINK_MARK],
      [LINK_MARK],
    ])
    expect(reopened.getMarkdown()).toBe(markdownOnSave)

    reopened.destroy()
  })

  test('saves a link around text and an image without a dangling bracket', () => {
    const editor = createEditor(`[see ![alt][${NAME}](${URL})](${LINK})`, true)

    expect(editor.getMarkdown()).toBe(
      `[see](${LINK}) [![alt][${NAME}](${URL})](${LINK})`
    )

    editor.destroy()
  })

  test('keeps the link of an external badge through an in-editor copy/paste', () => {
    const source = createEditor(BADGE, true)
    const target = createEditor('', true)

    target.commands.insertContent(source.getHTML())

    expect(target.getMarkdown()).toBe(BADGE)

    source.destroy()
    target.destroy()
  })

  test('does not link an image next to a link', () => {
    const markdown = `[see](${LINK}) ![alt][${NAME}](${URL})`
    const editor = createEditor(markdown, true)

    expect(imageJSON(editor)[0].marks).toBeUndefined()
    expect(editor.getMarkdown()).toBe(markdown)

    editor.destroy()
  })
})

describe('Pending image uploads', () => {
  const USER_FILE_NAME = `${'a'.repeat(32)}_${'b'.repeat(64)}.png`
  const USER_FILE_URL = `https://example.com/media/user_files/${USER_FILE_NAME}`
  const UPLOADED_ATTRS = {
    src: USER_FILE_URL,
    alt: 'shot',
    userFileName: USER_FILE_NAME,
  }

  const insertPending = (editor, pos, uploadIds) =>
    editor.view.dispatch(insertPendingImages(editor.state.tr, pos, uploadIds))

  const endOfText = (editor) => editor.state.doc.content.size - 1

  test('renders a loading placeholder that requests nothing', () => {
    const editor = createEditor('intro', true)

    insertPending(editor, endOfText(editor), ['upload-1'])

    expect(
      editor.view.dom.querySelectorAll('.rich-text-editor__image-uploading')
    ).toHaveLength(1)
    expect(editor.view.dom.querySelector('img')).toBeNull()
    expect(editor.view.dom.querySelector('[src]')).toBeNull()

    editor.destroy()
  })

  test('leaves no trace in the Markdown', () => {
    const editor = createEditor('intro', true)

    insertPending(editor, endOfText(editor), ['upload-1', 'upload-2'])

    expect(editor.getMarkdown()).toBe('intro')

    editor.destroy()
  })

  test('inserts the images in order and puts the caret after them', () => {
    const editor = createEditor('intro', true)
    editor.commands.setTextSelection(1)

    insertPending(editor, endOfText(editor), ['upload-1', 'upload-2'])

    expect(
      findPendingImages(editor.state.doc).map(({ node }) => node.attrs.uploadId)
    ).toEqual(['upload-1', 'upload-2'])
    expect(editor.state.selection.empty).toBe(true)
    expect(editor.state.selection.from).toBe(endOfText(editor))

    editor.destroy()
  })

  test('inserts after a code block instead of splitting it', () => {
    const editor = createEditor('```\nconst a = 1\n```', true)

    insertPending(editor, 5, ['upload-1'])

    const blocks = editor.state.doc.content.content
    expect(blocks.map((block) => block.type.name)).toEqual([
      'codeBlock',
      'paragraph',
    ])
    expect(blocks[0].textContent).toBe('const a = 1')
    expect(blocks[1].firstChild.attrs.uploadId).toBe('upload-1')

    editor.destroy()
  })

  test('never takes an upload id from pasted HTML', () => {
    registerTrustedImageUrl(USER_FILE_URL)
    const editor = createEditor('', true)

    editor.commands.insertContent(
      `<img src="${USER_FILE_URL}" alt="x" data-user-file-name="${USER_FILE_NAME}" uploadid="upload-1" data-upload-id="upload-1">`
    )

    expect(findImageNodes(editor)).toHaveLength(1)
    expect(findPendingImages(editor.state.doc)).toHaveLength(0)

    editor.destroy()
  })

  test('settles an upload in place without moving the caret', () => {
    registerTrustedImageUrl(USER_FILE_URL)
    const editor = createEditor('intro', true)
    insertPending(editor, endOfText(editor), ['upload-1'])
    editor.commands.insertContent('more')
    const selection = editor.state.selection.toJSON()

    editor.commands.settlePendingImage('upload-1', UPLOADED_ATTRS)

    expect(editor.state.selection.toJSON()).toEqual(selection)
    expect(findPendingImages(editor.state.doc)).toHaveLength(0)
    expect(editor.view.dom.querySelector('img').getAttribute('src')).toBe(
      USER_FILE_URL
    )
    expect(editor.getMarkdown()).toBe(
      `intro![shot][${USER_FILE_NAME}](${USER_FILE_URL})more`
    )

    editor.destroy()
  })

  test('removes the placeholder of a failed upload', () => {
    const editor = createEditor('intro', true)
    insertPending(editor, endOfText(editor), ['upload-1'])

    editor.commands.settlePendingImage('upload-1', null)

    expect(findImageNodes(editor)).toHaveLength(0)
    expect(editor.getMarkdown()).toBe('intro')

    editor.destroy()
  })

  test('removes the paragraph made for a failed upload after a code block', () => {
    const code = '```\nconst a = 1\n```'
    const editor = createEditor(code, true)
    insertPending(editor, 5, ['upload-1'])

    editor.commands.settlePendingImage('upload-1', null)

    expect(
      editor.state.doc.content.content.map((block) => block.type.name)
    ).toEqual(['codeBlock'])
    expect(editor.getMarkdown()).toBe(code)

    editor.destroy()
  })

  test('keeps a blank line a failed upload was pasted into', () => {
    const editor = createEditor('intro\n\n\n\noutro', true)
    insertPending(editor, 8, ['upload-1'])

    editor.commands.settlePendingImage('upload-1', null)

    expect(editor.getMarkdown()).toBe('intro\n\n\n\noutro')

    editor.destroy()
  })

  test('does not walk the document for edits that bring no pending image back', () => {
    registerTrustedImageUrl(USER_FILE_URL)
    const editor = createEditor('intro', true)
    insertPending(editor, endOfText(editor), ['upload-1'])
    editor.commands.settlePendingImage('upload-1', UPLOADED_ATTRS)
    const descendants = vi.spyOn(
      editor.state.doc.constructor.prototype,
      'descendants'
    )

    editor.commands.insertContent('more')

    expect(descendants).not.toHaveBeenCalled()
    descendants.mockRestore()
    editor.destroy()
  })

  test('undo removes an uploaded image and redo brings it back uploaded', () => {
    registerTrustedImageUrl(USER_FILE_URL)
    const editor = createEditor('intro', true)
    insertPending(editor, endOfText(editor), ['upload-1'])
    editor.commands.settlePendingImage('upload-1', UPLOADED_ATTRS)

    editor.commands.undo()

    expect(findImageNodes(editor)).toHaveLength(0)

    editor.commands.redo()

    expect(findPendingImages(editor.state.doc)).toHaveLength(0)
    expect(editor.getMarkdown()).toBe(
      `intro![shot][${USER_FILE_NAME}](${USER_FILE_URL})`
    )

    editor.destroy()
  })

  test.each([
    ['uploaded', UPLOADED_ATTRS, 1],
    ['failed', null, 0],
  ])(
    'undoing the deletion of a placeholder whose upload %s since settles it',
    (_, attrs, imageCount) => {
      registerTrustedImageUrl(USER_FILE_URL)
      const editor = createEditor('intro', true)
      insertPending(editor, endOfText(editor), ['upload-1'])
      editor.view.dispatch(closeHistory(editor.state.tr))
      editor.commands.deleteRange({
        from: endOfText(editor) - 1,
        to: endOfText(editor),
      })
      editor.commands.settlePendingImage('upload-1', attrs)

      editor.commands.undo()

      expect(findPendingImages(editor.state.doc)).toHaveLength(0)
      expect(findImageNodes(editor)).toHaveLength(imageCount)

      editor.destroy()
    }
  )

  test('drops pending images, and the paragraphs made for them, from JSON', () => {
    const pending = {
      type: 'image',
      attrs: { uploadId: 'upload-1', ownParagraph: false },
    }
    const pendingInOwnParagraph = {
      type: 'image',
      attrs: { uploadId: 'upload-2', ownParagraph: true },
    }
    const uploaded = {
      type: 'image',
      attrs: { ...UPLOADED_ATTRS, uploadId: null, ownParagraph: false },
    }

    expect(
      withoutPendingImages({
        type: 'doc',
        content: [
          {
            type: 'paragraph',
            content: [{ type: 'text', text: 'intro' }, pending, uploaded],
          },
          { type: 'paragraph', content: [pendingInOwnParagraph, pending] },
          { type: 'paragraph', content: [pending] },
          {
            type: 'paragraph',
            content: [pendingInOwnParagraph, { type: 'text', text: 'typed' }],
          },
        ],
      })
    ).toEqual({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [{ type: 'text', text: 'intro' }, uploaded],
        },
        { type: 'paragraph' },
        { type: 'paragraph', content: [{ type: 'text', text: 'typed' }] },
      ],
    })
    expect(
      withoutPendingImages({
        type: 'doc',
        content: [{ type: 'paragraph', content: [pendingInOwnParagraph] }],
      })
    ).toEqual({ type: 'doc', content: [{ type: 'paragraph' }] })
  })
})
