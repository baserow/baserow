import {
  preprocessRichTextImages,
  stripImageUrls,
  replaceImagesWithPlaceholder,
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
    expect(replaceImagesWithPlaceholder('![](abc_def.png)')).toBe(
      '![](abc_def.png)'
    )
    expect(replaceImagesWithPlaceholder('![][abc_def.png]')).toBe('🖼')
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
