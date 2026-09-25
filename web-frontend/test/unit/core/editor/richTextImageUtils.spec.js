import {
  countImageReferences,
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

describe('trimUnfinishedImageRef', () => {
  const name =
    'R7SiH9lsCNSxDKLRsabcjoqpu3YmYdmP_31f3aa68afe0ddc9027c18de4030fdb7df1434c10401ca23aab07d6fc308661c.png'
  const url = `https://s3.example.com/user_files/${name}`

  test.each([
    ['text ![alt', 'text '],
    ['text ![alt][abc_def.pn', 'text '],
    ['text ![alt][abc_def.png](https://exa', 'text '],
    ['text ![alt](https://exa', 'text '],
    [String.raw`text ![a\]b][abc_d`, 'text '],
    ['text ![line one\nline two', 'text '],
    [`text ![line one\nline two][${name.slice(0, 40)}`, 'text '],
    [`text ![line one\nline two][${name}](${url.slice(0, 30)}`, 'text '],
    [`text ![line one\nline two](${url.slice(0, 30)}`, 'text '],
    ['text ![alt]', 'text '],
    ['text ![line one\nline two]', 'text '],
    [String.raw`text ![a\]b]`, 'text '],
    ['text ![al\\', 'text '],
  ])('drops the cut-off token in %j', (input, expected) => {
    expect(trimUnfinishedImageRef(input)).toBe(expected)
  })

  test.each([
    'plain text',
    '![a][abc_def.png](https://example.com/f.png) tail',
    '![a][abc_def.png](https://example.com/f.png)',
    '![a](https://example.com/f.png) and ![b][x_y.png]',
    '![a][x_y.png] then [a link](https://example.com)',
    `![line one\nline two][${name}]`,
    `![line one\nline two][${name}](${url})`,
    '![a] is not an image',
    'see [a note]',
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

  test('accepts svg files by their stored name even though the backend does not flag them', () => {
    expect(
      isRenderableUserFile({
        is_image: false,
        name: 'abc123_def456.svg',
        original_name: 'logo.svg',
      })
    ).toBe(true)
    expect(
      isRenderableUserFile({ is_image: false, name: 'abc123_def456.svgz' })
    ).toBe(true)
  })

  test('accepts an uppercase svg extension', () => {
    expect(
      isRenderableUserFile({
        is_image: false,
        name: 'abc123_def456.SVG',
        original_name: 'LOGO.SVG',
      })
    ).toBe(true)
  })

  test('rejects non-image files', () => {
    expect(
      isRenderableUserFile({
        is_image: false,
        name: 'abc123_def456.pdf',
        original_name: 'doc.pdf',
      })
    ).toBe(false)
    expect(
      isRenderableUserFile({
        is_image: false,
        name: 'abc123_def456.pdf',
        original_name: 'doc.svg.pdf',
      })
    ).toBe(false)
    expect(
      isRenderableUserFile({ is_image: false, name: 'abc123_def456.' })
    ).toBe(false)
    expect(isRenderableUserFile(null)).toBe(false)
  })

  test('ignores original_name so it cannot disagree with the backend', () => {
    expect(
      isRenderableUserFile({
        is_image: false,
        name: 'abc123_def456.pdf',
        original_name: 'trick.svg',
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
})

describe('code and references are read exactly like the backend', () => {
  // A character only one of Python or JS treats as whitespace or a line break
  // would let the backend keep a URL the frontend then trusts.
  const url = 'https://e.com/p.png'

  test('a fence inside a list item is code', () => {
    const content = `- item\n\n  \`\`\`\n  ![x][abc_def.png](${url})\n  \`\`\`\n`
    expect(stripImageUrls(content)).toBe(content)
  })

  test.each(['\r', '\x1c', ' '])('only \\n ends a line (%j)', (char) => {
    const content = `x${char}\`\`\`\n![a][abc_def.png](${url})`
    expect(stripImageUrls(content)).toBe(`x${char}\`\`\`\n![a][abc_def.png]`)
  })

  test.each(['\x1c', ' ', '﻿'])(
    'only spaces and tabs may follow a closing fence (%j)',
    (char) => {
      const content = `\`\`\`\ncode\n\`\`\`${char}\n![a][abc_def.png](${url})`
      expect(Array.from(iterCodeSegments(content))).toEqual([[content, true]])
    }
  )

  test.each(['\x1c', '\x1f', '\x85', ' ', '﻿'])(
    'non-ASCII whitespace is part of the name (%j)',
    (char) => {
      const content = `![a][abc_def.png${char}](${url})`
      expect(stripImageUrls(content)).toBe(`![a][abc_def.png${char}]`)
      expect(preprocessRichTextImages(content).nameMap).toEqual({
        [url]: `abc_def.png${char}`,
      })
    }
  )

  test.each(['\x1c', ' ', '﻿'])(
    'non-ASCII whitespace is part of the URL (%j)',
    (char) => {
      const content = `![a][abc_def.png](https://e.com/p${char}.png)`
      expect(stripImageUrls(content)).toBe('![a][abc_def.png]')
    }
  )
})

describe('countImageReferences', () => {
  const name =
    'R7SiH9lsCNSxDKLRsabcjoqpu3YmYdmP_31f3aa68afe0ddc9027c18de4030fdb7df1434c10401ca23aab07d6fc308661c.png'

  // Same cases as TestCountImageReferences in test_rich_text_utils.py.
  test.each([
    [null, 0],
    ['', 0],
    [`![a][${name}]`, 1],
    [`![a][${name}] ![a][${name}]`, 2],
    [`![a][${name}](https://h/x.png)`, 1],
    [`\`![a][${name}]\` ![b][${name}]`, 1],
    [`\`\`\`\n![a][${name}]\n\`\`\`\n![b][${name}]`, 1],
    [`x\r\`\`\`\n![a][${name}]`, 1],
    [`!\\[a][${name}]`, 0],
    [`![a\\]b][${name}]`, 1],
    [`![a][${name}\u2028]`, 1],
    ['![a](https://e.com/p.png)', 0],
  ])('%j has %i', (content, expected) => {
    expect(countImageReferences(content)).toBe(expected)
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
  // Best of three: a parallel test run can stall any single timing.
  const time = (fn, input) =>
    Math.min(
      ...[0, 1, 2].map(() => {
        const start = performance.now()
        fn(input)
        return performance.now() - start
      })
    )
  const functions = {
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
    multiLineAlts: (n) => '![x\n'.repeat(n) + '].',
    bareMultiLineAlts: (n) => '![x\n]'.repeat(n) + '.',
    escapedMultiLineAlt: (n) => '![' + '\\x\n'.repeat(n) + '].',
  }

  describe.each(Object.keys(functions))('%s', (fnName) => {
    test.each(Object.keys(inputs))('on %s', (inputName) => {
      const fn = functions[fnName]
      const input = inputs[inputName]
      // Warm up so JIT compilation does not count against the smaller run.
      fn(input(1000))
      const small = time(fn, input(N))
      const large = time(fn, input(2 * N))
      expect(large).toBeLessThan(3 * small + 200)
      expect(large).toBeLessThan(2000)
    })
  })
})
