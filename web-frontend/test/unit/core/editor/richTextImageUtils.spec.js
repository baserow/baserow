import {
  demoteExternalImagesToLinks,
  isRenderableUserFile,
  iterCodeSegments,
  preprocessRichTextImages,
  stripImageUrls,
  stripUnresolvedImageRefs,
  replaceImagesWithPlaceholder,
  sanitizeUploadFileName,
  imageUploadType,
  isImageUploadCandidate,
  trimUnfinishedImageRef,
  IMAGE_PLACEHOLDER,
} from '@baserow/modules/core/editor/richTextImageUtils'
import { parseMarkdown } from '@baserow/modules/core/editor/markdown'

describe('preprocessRichTextImages', () => {
  test('returns empty content and nameMap for null', () => {
    const result = preprocessRichTextImages(null)
    expect(result).toEqual({ content: '', nameMap: {} })
  })

  test('returns empty content and nameMap for empty string', () => {
    const result = preprocessRichTextImages('')
    expect(result).toEqual({ content: '', nameMap: {} })
  })

  test('passes through content without images', () => {
    const result = preprocessRichTextImages('Hello **bold** world')
    expect(result).toEqual({ content: 'Hello **bold** world', nameMap: {} })
  })

  test('converts custom format to standard markdown and builds nameMap', () => {
    const result = preprocessRichTextImages(
      '![alt][abc123_def456.png](https://example.com/file.png)'
    )
    expect(result.content).toBe('![alt](https://example.com/file.png)')
    expect(result.nameMap).toEqual({
      'https://example.com/file.png': 'abc123_def456.png',
    })
  })

  test('handles multiple images', () => {
    const input =
      '![a][f1_h1.png](https://cdn.com/1.png) text ![b][f2_h2.jpg](https://cdn.com/2.jpg)'
    const result = preprocessRichTextImages(input)
    expect(result.content).toBe(
      '![a](https://cdn.com/1.png) text ![b](https://cdn.com/2.jpg)'
    )
    expect(result.nameMap).toEqual({
      'https://cdn.com/1.png': 'f1_h1.png',
      'https://cdn.com/2.jpg': 'f2_h2.jpg',
    })
  })

  test('handles escaped brackets in alt text', () => {
    const result = preprocessRichTextImages(
      String.raw`![my\]pic][abc_def.png](https://example.com/f.png)`
    )
    expect(result.content).toBe(
      String.raw`![my\]pic](https://example.com/f.png)`
    )
    expect(result.nameMap).toEqual({
      'https://example.com/f.png': 'abc_def.png',
    })
  })

  test('does not match user file names containing path separators', () => {
    const input = [
      '![x][abc_def.png/../evil.png](https://example.com/e.png)',
      String.raw`![x][abc_def.png\..\evil.png](https://example.com/e.png)`,
    ].join(' ')
    const result = preprocessRichTextImages(input)
    expect(result.content).toBe(input)
    expect(result.nameMap).toEqual({})
  })

  test('does not match user file names containing parentheses', () => {
    const input = '![x][abc_def.png)](https://example.com/abc_def.png))'
    const result = preprocessRichTextImages(input)
    expect(result.content).toBe(input)
    expect(result.nameMap).toEqual({})
  })

  test('does not convert plain markdown images', () => {
    const input = '![alt](https://example.com/file.png)'
    expect(preprocessRichTextImages(input)).toEqual({
      content: input,
      nameMap: {},
    })
  })
})

describe('stripUnresolvedImageRefs', () => {
  test('does not match user file names containing path separators', () => {
    const input = '![x][abc_def.png/../evil.png]'
    expect(stripUnresolvedImageRefs(input)).toBe(input)
  })
})

describe('demoteExternalImagesToLinks', () => {
  test('returns empty string for null', () => {
    expect(demoteExternalImagesToLinks(null)).toBe('')
  })

  test('returns content unchanged without images', () => {
    expect(demoteExternalImagesToLinks('Hello [link](https://a.com)')).toBe(
      'Hello [link](https://a.com)'
    )
  })

  test('demotes an https image', () => {
    expect(
      demoteExternalImagesToLinks(
        'see ![alt](https://example.com/photo.png) now'
      )
    ).toBe('see [alt](https://example.com/photo.png) now')
  })

  test('demotes an http image', () => {
    expect(
      demoteExternalImagesToLinks('![alt](http://example.com/photo.png)')
    ).toBe('[alt](http://example.com/photo.png)')
  })

  test('downgrades unsafe schemes to links', () => {
    expect(demoteExternalImagesToLinks('![](javascript:alert(1))')).toBe(
      '[](javascript:alert(1))'
    )
    expect(
      demoteExternalImagesToLinks('![x](data:image/png;base64,AAAA)')
    ).toBe('[x](data:image/png;base64,AAAA)')
  })

  test('does not touch Baserow image refs', () => {
    const withUrl = '![alt][abc123_def456.png](https://example.com/f.png)'
    const withoutUrl = '![alt][abc123_def456.png]'
    expect(demoteExternalImagesToLinks(withUrl)).toBe(withUrl)
    expect(demoteExternalImagesToLinks(withoutUrl)).toBe(withoutUrl)
  })

  test('handles escaped brackets in alt text', () => {
    expect(
      demoteExternalImagesToLinks(
        String.raw`![my\]pic](https://example.com/f.png)`
      )
    ).toBe(String.raw`[my\]pic](https://example.com/f.png)`)
  })

  // The Baserow ref keeps its image form; only the plain one is demoted.
  test('handles a mix of Baserow refs and external images', () => {
    expect(
      demoteExternalImagesToLinks(
        '![a][f1_h1.png](https://cdn.com/1.png) ![b](https://example.com/2.png)'
      )
    ).toBe(
      '![a][f1_h1.png](https://cdn.com/1.png) [b](https://example.com/2.png)'
    )
  })

  test('downgrades ftp to link', () => {
    expect(demoteExternalImagesToLinks('![x](ftp://a.com/x.png)')).toBe(
      '[x](ftp://a.com/x.png)'
    )
  })
})

describe('trimUnfinishedImageRef', () => {
  test.each([
    ['text ![alt', 'text '],
    ['text ![alt][abc_def.pn', 'text '],
    ['text ![alt][abc_def.png](https://exa', 'text '],
    ['text ![alt](https://exa', 'text '],
    [String.raw`text ![a\]b][abc_d`, 'text '],
  ])('drops the cut-off token in %j', (input, expected) => {
    expect(trimUnfinishedImageRef(input)).toBe(expected)
  })

  test.each([
    'plain text',
    '![a][abc_def.png](https://example.com/f.png) tail',
    '![a][abc_def.png](https://example.com/f.png)',
    '![a](https://example.com/f.png) and ![b][x_y.png]',
    '![a][x_y.png] then [a link](https://example.com)',
  ])('keeps complete content %j', (input) => {
    expect(trimUnfinishedImageRef(input)).toBe(input)
  })

  test('returns empty string for null', () => {
    expect(trimUnfinishedImageRef(null)).toBe('')
  })
})

describe('isRenderableUserFile', () => {
  test('accepts files flagged as image by the backend', () => {
    expect(
      isRenderableUserFile({ is_image: true, original_name: 'photo.png' })
    ).toBe(true)
  })

  test('accepts svg files even though the backend does not flag them', () => {
    expect(
      isRenderableUserFile({ is_image: false, original_extension: 'svg' })
    ).toBe(true)
    expect(
      isRenderableUserFile({ is_image: false, original_extension: 'SVGZ' })
    ).toBe(true)
  })

  test('rejects non-image files', () => {
    expect(
      isRenderableUserFile({ is_image: false, original_extension: 'pdf' })
    ).toBe(false)
    expect(
      isRenderableUserFile({
        is_image: false,
        original_name: 'doc.svg.pdf',
        original_extension: 'pdf',
      })
    ).toBe(false)
    expect(isRenderableUserFile(null)).toBe(false)
  })

  test('ignores original_name so it cannot disagree with the backend', () => {
    // Backend only checks original_extension; a name ending in .svg with a
    // different extension must be rejected here too.
    expect(
      isRenderableUserFile({
        is_image: false,
        original_name: 'trick.svg',
        original_extension: 'pdf',
      })
    ).toBe(false)
    expect(
      isRenderableUserFile({ is_image: false, original_name: 'logo.svg' })
    ).toBe(false)
  })
})

describe('stripImageUrls', () => {
  test('returns empty string for null', () => {
    expect(stripImageUrls(null)).toBe('')
  })

  test('returns content unchanged without images', () => {
    expect(stripImageUrls('Hello world')).toBe('Hello world')
  })

  test('strips URL from image reference', () => {
    expect(
      stripImageUrls('![photo][abc123_def456.png](https://example.com/f.png)')
    ).toBe('![photo][abc123_def456.png]')
  })

  test('strips multiple URLs', () => {
    const input =
      '![a][f1_h1.png](https://cdn.com/1.png) ![b][f2_h2.jpg](https://cdn.com/2.jpg)'
    expect(stripImageUrls(input)).toBe('![a][f1_h1.png] ![b][f2_h2.jpg]')
  })

  test('handles escaped brackets in alt text', () => {
    expect(
      stripImageUrls(
        String.raw`![my\]pic][abc_def.png](https://example.com/f.png)`
      )
    ).toBe(String.raw`![my\]pic][abc_def.png]`)
  })
})

describe('replaceImagesWithPlaceholder', () => {
  test('returns empty string for null', () => {
    expect(replaceImagesWithPlaceholder(null)).toBe('')
  })

  test('returns content unchanged without images', () => {
    expect(replaceImagesWithPlaceholder('Hello world')).toBe('Hello world')
  })

  test('replaces image with URL with placeholder', () => {
    expect(
      replaceImagesWithPlaceholder(
        '![photo][abc123_def456.png](https://example.com/f.png)'
      )
    ).toBe('🖼︎ photo')
  })

  test('replaces image without URL with placeholder', () => {
    expect(replaceImagesWithPlaceholder('![photo][abc123_def456.png]')).toBe(
      '🖼︎ photo'
    )
  })

  test('uses generic placeholder when alt is empty', () => {
    expect(replaceImagesWithPlaceholder('![](abc_def.png)')).toBe('🖼︎')
    expect(replaceImagesWithPlaceholder('![][abc_def.png]')).toBe('🖼︎')
  })

  test('replaces external image with placeholder', () => {
    expect(
      replaceImagesWithPlaceholder('![photo](https://example.com/photo.png)')
    ).toBe('🖼︎ photo')
  })

  test('replaces multiple images', () => {
    const input = 'Before ![a][f1_h1.png] middle ![b][f2_h2.jpg] after'
    expect(replaceImagesWithPlaceholder(input)).toBe(
      'Before 🖼︎ a middle 🖼︎ b after'
    )
  })

  test('handles escaped brackets in alt text', () => {
    expect(
      replaceImagesWithPlaceholder(String.raw`![my\]pic][abc_def.png]`)
    ).toBe(String.raw`🖼︎ my\]pic`)
  })
})

describe('iterCodeSegments', () => {
  test('splits inline spans and fences out of the text', () => {
    const content = 'a `b` c\n```\nd\n```\ne'
    expect([...iterCodeSegments(content)]).toEqual([
      ['a ', false],
      ['`b`', true],
      [' c\n', false],
      ['```\nd\n```\n', true],
      ['e', false],
    ])
  })

  test('a span closes only on a run of the same length', () => {
    expect([...iterCodeSegments('``a ` b`` c')]).toEqual([
      ['``a ` b``', true],
      [' c', false],
    ])
    expect([...iterCodeSegments('a ` b')]).toEqual([['a ` b', false]])
  })

  test('a fence closes only on the same char and at least the same length', () => {
    expect([...iterCodeSegments('~~~\ncode\n~~~~\nafter')]).toEqual([
      ['~~~\ncode\n~~~~\n', true],
      ['after', false],
    ])
    const unclosed = '````\n~~~\n```\nstill code'
    expect([...iterCodeSegments(unclosed)]).toEqual([[unclosed, true]])
  })

  test('is linear on runs that never pair up', () => {
    const content = Array.from({ length: 2000 }, (_, n) =>
      '`'.repeat(n + 1)
    ).join(' ')
    const start = performance.now()
    expect([...iterCodeSegments(content)]).toEqual([[content, false]])
    expect(performance.now() - start).toBeLessThan(1000)
  })
})

describe('image syntax inside code is literal', () => {
  const ref = '![x][abc_def.png]'
  const resolved = `${ref}(http://h/abc_def.png)`
  const ext = '![x](https://e.com/a.png)'

  test('preprocessRichTextImages', () => {
    const { content, nameMap } = preprocessRichTextImages(
      `\`${resolved}\` ${resolved}`
    )
    expect(content).toBe(`\`${resolved}\` ![x](http://h/abc_def.png)`)
    expect(nameMap).toEqual({ 'http://h/abc_def.png': 'abc_def.png' })
  })

  test('stripImageUrls', () => {
    expect(stripImageUrls(`\`${resolved}\` ${resolved}`)).toBe(
      `\`${resolved}\` ${ref}`
    )
  })

  test('stripUnresolvedImageRefs and replaceImagesWithPlaceholder', () => {
    expect(stripUnresolvedImageRefs(`\`${ref}\` ${ref}`)).toBe(
      `\`${ref}\` ${IMAGE_PLACEHOLDER} x`
    )
    expect(
      replaceImagesWithPlaceholder(`\`\`\`\n${ref}\n${ext}\n\`\`\`\n${ext}`)
    ).toBe(`\`\`\`\n${ref}\n${ext}\n\`\`\`\n${IMAGE_PLACEHOLDER} x`)
  })

  test('demoteExternalImagesToLinks', () => {
    expect(demoteExternalImagesToLinks(`\`${ext}\` ${ext}`)).toBe(
      `\`${ext}\` [x](https://e.com/a.png)`
    )
  })
})

describe('image syntax inside block code found by markdown-it is literal', () => {
  const ext = '![x](http://a)'
  const ref = '![x][abc_def.png](http://h/abc_def.png)'

  test('four-space indented code keeps the leading `!`', () => {
    const content = `    ${ext}`
    expect(demoteExternalImagesToLinks(content)).toBe(content)
    expect(replaceImagesWithPlaceholder(content)).toBe(content)
    const html = parseMarkdown(content, { enableImages: true })
    expect(html).toContain(`<pre><code>${ext}`)
  })

  test('an indented line continuing a paragraph is not code', () => {
    expect(demoteExternalImagesToLinks(`text\n    ${ext}`)).toBe(
      'text\n    [x](http://a)'
    )
  })

  test('a fence inside a list item is code', () => {
    const content = `- item\n\n  \`\`\`\n  ${ext}\n  ${ref}\n  \`\`\`\n\n${ext}`
    expect(demoteExternalImagesToLinks(content)).toBe(
      content.replace(/\n\n!\[x\]\(http:\/\/a\)$/, '\n\n[x](http://a)')
    )
    expect(stripImageUrls(content)).toBe(content)
    const html = parseMarkdown(content, { enableImages: true })
    expect(html).toContain(ext)
    expect(html).toContain(ref)
  })

  test('indented code inside a blockquote is code', () => {
    const content = `>     ${ext}`
    expect(demoteExternalImagesToLinks(content)).toBe(content)
  })

  test('CR and CRLF line endings split lines like markdown-it', () => {
    const content = `a\r\n\r\n    ${ext}\r\rb ${ext}`
    expect(demoteExternalImagesToLinks(content)).toBe(
      `a\r\n\r\n    ${ext}\r\rb [x](http://a)`
    )
  })
})

describe('user file names without an extension', () => {
  const ref = '![x][abc_def.]'
  const resolved = `${ref}(http://h/abc_def.)`

  test('round-trip through the helpers', () => {
    expect(stripImageUrls(resolved)).toBe(ref)
    const { content, nameMap } = preprocessRichTextImages(resolved)
    expect(content).toBe('![x](http://h/abc_def.)')
    expect(nameMap).toEqual({ 'http://h/abc_def.': 'abc_def.' })
    expect(stripUnresolvedImageRefs(ref)).toBe(`${IMAGE_PLACEHOLDER} x`)
    expect(replaceImagesWithPlaceholder(resolved)).toBe(
      `${IMAGE_PLACEHOLDER} x`
    )
  })

  test('render as an image in the preview', () => {
    const html = parseMarkdown(resolved, { enableImages: true })
    expect(html).toContain('<img src="http://h/abc_def."')
  })
})

describe('sanitizeUploadFileName', () => {
  test.each([
    ['a.jpg)', 'a.jpg'],
    ['photo.png)', 'photo.png'],
    ['photo.p n]g', 'photo.png'],
    ['photo.pn/g\\(', 'photo.png'],
    ['my (1).png', 'my (1).png'],
    ['noextension', 'noextension'],
    ['trailing.', 'trailing.'],
  ])('%j becomes %j', (input, expected) => {
    expect(sanitizeUploadFileName(input)).toBe(expected)
  })
})

describe('imageUploadType', () => {
  test.each([
    ['photo.png', 'image/png', 'image/png'],
    ['doc.pdf', 'application/pdf', null],
    ['photo.jpg)', '', 'image/jpeg'],
    ['photo.JPEG', '', 'image/jpeg'],
    ['logo.svg', '', 'image/svg+xml'],
    ['notes.txt)', '', null],
    ['noextension', '', null],
  ])('%j with type %j is %j', (name, type, expected) => {
    expect(imageUploadType(new File(['x'], name, { type }))).toBe(expected)
  })

  test('null file', () => {
    expect(imageUploadType(null)).toBe(null)
  })
})

describe('isImageUploadCandidate', () => {
  test.each([
    ['photo.png', 'image/png', true],
    ['photo', '', true],
    ['photo.jpg)', '', true],
    ['notes.txt', 'text/plain', false],
    ['doc.pdf', 'application/pdf', false],
  ])('%j with type %j is %j', (name, type, expected) => {
    expect(isImageUploadCandidate(new File(['x'], name, { type }))).toBe(
      expected
    )
  })

  test('null file', () => {
    expect(isImageUploadCandidate(null)).toBe(false)
  })
})

describe('image regexes are linear', () => {
  // A quadratic scan at these sizes takes seconds; a linear one milliseconds.
  const N = 20000
  const time = (fn, input) => {
    const start = performance.now()
    fn(input)
    return performance.now() - start
  }
  const functions = {
    demoteExternalImagesToLinks,
    stripImageUrls,
    preprocessRichTextImages,
    replaceImagesWithPlaceholder,
    trimUnfinishedImageRef,
    parseMarkdown: (value) => parseMarkdown(value, { enableImages: true }),
    parseMarkdownWithoutImages: (value) => parseMarkdown(value),
  }
  const inputs = {
    plain: (n) => '![x]('.repeat(n),
    plainClosedAtEnd: (n) => '![x]('.repeat(n) + ')',
    withUrl: (n) => '![x][a_b.png]('.repeat(n),
    withUrlClosedAtEnd: (n) => '![x][a_b.png]('.repeat(n) + ')',
    deepParens: (n) => '![x](' + '('.repeat(n),
  }

  describe.each(Object.keys(functions))('%s', (fnName) => {
    test.each(Object.keys(inputs))('on %s', (inputName) => {
      const fn = functions[fnName]
      const input = inputs[inputName]
      // Warm up so JIT compilation does not count against the smaller run.
      fn(input(1000))
      const small = time(fn, input(N))
      const large = time(fn, input(2 * N))
      expect(large).toBeLessThan(3 * small + 100)
      expect(large).toBeLessThan(2000)
    })
  })
})
