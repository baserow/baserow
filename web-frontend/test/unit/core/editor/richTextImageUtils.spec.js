import {
  validateExternalImageProtocols,
  isRenderableUserFile,
  preprocessRichTextImages,
  stripImageUrls,
  stripUnresolvedImageRefs,
  replaceImagesWithPlaceholder,
  trimUnfinishedImageRef,
} from '@baserow/modules/core/editor/richTextImageUtils'

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

describe('validateExternalImageProtocols', () => {
  test('returns empty string for null', () => {
    expect(validateExternalImageProtocols(null)).toBe('')
  })

  test('returns content unchanged without images', () => {
    expect(validateExternalImageProtocols('Hello [link](https://a.com)')).toBe(
      'Hello [link](https://a.com)'
    )
  })

  test('preserves https image', () => {
    const input = 'see ![alt](https://example.com/photo.png) now'
    expect(validateExternalImageProtocols(input)).toBe(input)
  })

  test('preserves http image', () => {
    const input = '![alt](http://example.com/photo.png)'
    expect(validateExternalImageProtocols(input)).toBe(input)
  })

  test('downgrades unsafe schemes to links', () => {
    expect(validateExternalImageProtocols('![](javascript:alert(1))')).toBe(
      '[](javascript:alert(1))'
    )
    expect(
      validateExternalImageProtocols('![x](data:image/png;base64,AAAA)')
    ).toBe('[x](data:image/png;base64,AAAA)')
  })

  test('does not touch Baserow image refs', () => {
    const withUrl = '![alt][abc123_def456.png](https://example.com/f.png)'
    const withoutUrl = '![alt][abc123_def456.png]'
    expect(validateExternalImageProtocols(withUrl)).toBe(withUrl)
    expect(validateExternalImageProtocols(withoutUrl)).toBe(withoutUrl)
  })

  test('handles escaped brackets in alt text', () => {
    expect(
      validateExternalImageProtocols(
        String.raw`![my\]pic](https://example.com/f.png)`
      )
    ).toBe(String.raw`![my\]pic](https://example.com/f.png)`)
  })

  test('handles a mix of Baserow refs and external images', () => {
    expect(
      validateExternalImageProtocols(
        '![a][f1_h1.png](https://cdn.com/1.png) ![b](https://example.com/2.png)'
      )
    ).toBe(
      '![a][f1_h1.png](https://cdn.com/1.png) ![b](https://example.com/2.png)'
    )
  })

  test('downgrades ftp to link', () => {
    expect(validateExternalImageProtocols('![x](ftp://a.com/x.png)')).toBe(
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
    ).toBe('🖼 photo')
  })

  test('replaces image without URL with placeholder', () => {
    expect(replaceImagesWithPlaceholder('![photo][abc123_def456.png]')).toBe(
      '🖼 photo'
    )
  })

  test('uses generic placeholder when alt is empty', () => {
    expect(replaceImagesWithPlaceholder('![](abc_def.png)')).toBe('🖼')
    expect(replaceImagesWithPlaceholder('![][abc_def.png]')).toBe('🖼')
  })

  test('replaces external image with placeholder', () => {
    expect(
      replaceImagesWithPlaceholder('![photo](https://example.com/photo.png)')
    ).toBe('🖼 photo')
  })

  test('replaces multiple images', () => {
    const input = 'Before ![a][f1_h1.png] middle ![b][f2_h2.jpg] after'
    expect(replaceImagesWithPlaceholder(input)).toBe(
      'Before 🖼 a middle 🖼 b after'
    )
  })

  test('handles escaped brackets in alt text', () => {
    expect(
      replaceImagesWithPlaceholder(String.raw`![my\]pic][abc_def.png]`)
    ).toBe(String.raw`🖼 my\]pic`)
  })
})
