import {
  getRichTextClipboardContent,
  LOCAL_STORAGE_CLIPBOARD_KEY,
} from '@baserow/modules/database/utils/clipboard'
import {
  clearTrustedImageUrls,
  isTrustedImageUrl,
} from '@baserow/modules/core/editor/trustedImageUrls'

describe('getRichTextClipboardContent', () => {
  afterEach(() => {
    localStorage.removeItem(LOCAL_STORAGE_CLIPBOARD_KEY)
    clearTrustedImageUrls()
  })

  test('trusts the image URLs of a copied rich text cell', () => {
    const value = '![x][abc_def.png](https://h/user_files/abc_def.png)'
    const text = `"${value}"`
    localStorage.setItem(
      LOCAL_STORAGE_CLIPBOARD_KEY,
      JSON.stringify({ text, json: [[{ richText: true, value }]] })
    )

    expect(getRichTextClipboardContent(text)).toBe(value)
    expect(isTrustedImageUrl('https://h/user_files/abc_def.png')).toBe(true)
  })

  test('trusts nothing when the clipboard does not match', () => {
    localStorage.setItem(
      LOCAL_STORAGE_CLIPBOARD_KEY,
      JSON.stringify({
        text: 'other',
        json: [[{ richText: true, value: '![x][abc_def.png](https://h/a)' }]],
      })
    )

    expect(getRichTextClipboardContent('pasted')).toBeNull()
    expect(isTrustedImageUrl('https://h/a')).toBe(false)
  })
})
