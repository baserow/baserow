import head from '@baserow/modules/core/head'
import {
  getCustomFaviconLinks,
  getDefaultFaviconKeys,
} from '@baserow/modules/builder/utils/favicon'

describe('Builder favicon util tests', () => {
  describe('getDefaultFaviconKeys', () => {
    test('returns the key of every default favicon link in head.js', () => {
      const keys = getDefaultFaviconKeys()

      // There should be at least one default favicon, and every one must
      // expose a key (otherwise unhead cannot dedupe and the builder's custom
      // favicon could never override it).
      expect(keys.length).toBeGreaterThan(0)
      keys.forEach((key) => expect(typeof key).toBe('string'))

      // The keys must exactly match the favicon links declared in head.js.
      const expected = head.link
        .filter((link) => link.rel === 'icon')
        .map((link) => link.key)
      expect(keys).toStrictEqual(expected)
    })
  })

  describe('getCustomFaviconLinks', () => {
    test('returns null when no custom favicon is uploaded, keeping the defaults', () => {
      expect(getCustomFaviconLinks({})).toBe(null)
      expect(getCustomFaviconLinks({ favicon_file: null })).toBe(null)
      // A favicon_file without a usable url should also fall back to defaults.
      expect(getCustomFaviconLinks({ favicon_file: {} })).toBe(null)
    })

    test('overrides every default favicon with the custom one', () => {
      const builder = {
        favicon_file: {
          url: 'https://example.com/media/custom-favicon.png',
          mime_type: 'image/png',
        },
      }

      const links = getCustomFaviconLinks(builder)

      // One override link is produced per default favicon...
      expect(links).toHaveLength(getDefaultFaviconKeys().length)

      // ...and the keys exactly match the defaults so unhead replaces them
      // rather than appending alongside them.
      expect(links.map((link) => link.key)).toStrictEqual(
        getDefaultFaviconKeys()
      )

      // Every override points at the uploaded custom favicon.
      links.forEach((link) => {
        expect(link).toStrictEqual({
          key: link.key,
          rel: 'icon',
          type: 'image/png',
          href: 'https://example.com/media/custom-favicon.png',
        })
      })
    })
  })
})
