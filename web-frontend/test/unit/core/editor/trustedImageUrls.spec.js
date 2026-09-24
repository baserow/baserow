import {
  clearTrustedImageUrls,
  isTrustedImageUrl,
  MAX_TRUSTED_IMAGE_URLS,
  registerTrustedImageUrl,
  registerTrustedImageUrlsFromMarkdown,
} from '@baserow/modules/core/editor/trustedImageUrls'

describe('trustedImageUrls', () => {
  afterEach(() => {
    clearTrustedImageUrls()
  })

  test('only registered URLs are trusted', () => {
    expect(isTrustedImageUrl('https://a.example.com/x.png')).toBe(false)
    registerTrustedImageUrl('https://a.example.com/x.png')
    expect(isTrustedImageUrl('https://a.example.com/x.png')).toBe(true)
    expect(isTrustedImageUrl('')).toBe(false)
    expect(isTrustedImageUrl(null)).toBe(false)
  })

  test('evicts the least recently used URL past the cap', () => {
    for (let i = 0; i < MAX_TRUSTED_IMAGE_URLS; i++) {
      registerTrustedImageUrl(`https://a.example.com/${i}.png`)
    }
    // A hit refreshes the entry, so the next oldest is evicted instead.
    expect(isTrustedImageUrl('https://a.example.com/0.png')).toBe(true)
    registerTrustedImageUrl('https://a.example.com/new.png')

    expect(isTrustedImageUrl('https://a.example.com/0.png')).toBe(true)
    expect(isTrustedImageUrl('https://a.example.com/1.png')).toBe(false)
    expect(isTrustedImageUrl('https://a.example.com/new.png')).toBe(true)
  })

  test('registers resolved references from Markdown, outside code only', () => {
    registerTrustedImageUrlsFromMarkdown(
      '![a][abc_def.png](https://h/abc_def.png) ' +
        '`![b][abc_ghi.png](https://h/abc_ghi.png)` ' +
        '![c](https://h/plain.png)'
    )

    expect(isTrustedImageUrl('https://h/abc_def.png')).toBe(true)
    expect(isTrustedImageUrl('https://h/abc_ghi.png')).toBe(false)
    expect(isTrustedImageUrl('https://h/plain.png')).toBe(false)
  })
})
