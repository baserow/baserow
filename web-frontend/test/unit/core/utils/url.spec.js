import {
  isRelativeUrl,
  parseHostnamesFromUrls,
} from '@baserow/modules/core/utils/url'
import {
  isValidAbsoluteURL,
  isValidURL,
  isValidURLWithHttpScheme,
} from '@baserow/modules/core/utils/string'

describe('test url utils', () => {
  describe('test isRelativeUrl', () => {
    const relativeUrls = ['/test', 'test/test', '/', '/dashboard?test=true']
    const absoluteUrls = [
      'http://example.com',
      'HTTP://EXAMPLE.COM',
      'https://www.exmaple.com',
      'ftp://example.com/file.txt',
      '//cdn.example.com/lib.js',
      'git+ssh://example.con/item',
      '////www.example.com',
      '////example.com',
      '///example.com',
    ]
    test.each(relativeUrls)('test with relative url %s', (url) => {
      expect(isRelativeUrl(url)).toBe(true)
    })
    test.each(absoluteUrls)('test with absolute url %s', (url) => {
      expect(isRelativeUrl(url)).toBe(false)
    })
  })
  describe('test is valid url', () => {
    const invalidURLs = [
      '/test',
      'test/test',
      '/',
      '/dashboard?test=true',
      'asdasd',
    ]
    const validURLs = [
      'http://example.com',
      'HTTP://EXAMPLE.COM',
      'https://www.exmaple.com',
      'ftp://example.com/file.txt',
      '//cdn.example.com/lib.js',
      'git+ssh://example.con/item',
    ]
    test.each(validURLs)('test with valid url %s', (url) => {
      expect(isValidURL(url)).toBe(true)
    })
    test.each(invalidURLs)('test with invalid url %s', (url) => {
      expect(isValidURL(url)).toBe(false)
    })
  })
  describe('test is valid https url', () => {
    const invalidURLs = [
      '/test',
      'test/test',
      '/',
      '/dashboard?test=true',
      'asdasd',
      'ftp://example.com/file.txt',
      '//cdn.example.com/lib.js',
      'git+ssh://example.con/item',
    ]
    const validURLs = [
      'https://example.com',
      'HTTPs://EXAMPLE.COM',
      'https://www.exmaple.com',
      'https://example.com/file.txt',
      'https://cdn.example.com/lib.js',
      'HtTps://example.con/item',
      'http://example.com',
      'HTTP://EXAMPLE.COM',
      'http://example.com',
      'http://example.com/file.txt',
      'http://cdn.example.com/lib.js',
      'HtTp://example.con/item',
    ]
    test.each(validURLs)('test with valid http/s url %s', (url) => {
      expect(isValidURLWithHttpScheme(url)).toBe(true)
    })
    test.each(invalidURLs)('test with invalid http/s url %s', (url) => {
      expect(isValidURLWithHttpScheme(url)).toBe(false)
    })
  })
  describe('test is valid absolute url', () => {
    const invalidURLs = [
      '/test',
      'test/test',
      '/',
      '/dashboard?test=true',
      'asdasd',
      'ftp://example.com/file.txt',
      '//cdn.example.com/lib.js',
      'git+ssh://example.con/item',
      'https://test',
    ]
    const validURLs = [
      'https://example.com',
      'HTTPs://EXAMPLE.COM',
      'https://www.exmaple.com',
      'https://example.com/file.txt',
      'https://cdn.example.com/lib.js',
      'HtTps://example.con/item',
      'http://example.com',
      'HTTP://EXAMPLE.COM',
      'http://example.com',
      'http://example.com/file.txt',
      'http://cdn.example.com/lib.js',
      'HtTp://example.con/item',
    ]
    test.each(validURLs)('test with valid http/s url %s', (url) => {
      expect(isValidAbsoluteURL(url)).toBe(true)
    })
    test.each(invalidURLs)('test with invalid http/s url %s', (url) => {
      expect(isValidAbsoluteURL(url)).toBe(false)
    })
  })
  describe('test parseHostnamesFromUrls', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {})

    afterEach(() => {
      warnSpy.mockClear()
    })

    afterAll(() => {
      warnSpy.mockRestore()
    })

    test.each([undefined, null, ''])(
      'returns [] for empty input (%s)',
      (value) => {
        expect(parseHostnamesFromUrls(value)).toEqual([])
        expect(warnSpy).not.toHaveBeenCalled()
      }
    )

    test('parses a comma-separated list, trims whitespace, skips blanks, and returns hostnames', () => {
      const input =
        ' https://example.com/path , http://sub.example.com:8080 ,   , https://example.co.uk?q=1 '

      expect(parseHostnamesFromUrls(input)).toEqual([
        'example.com',
        'sub.example.com',
        'example.co.uk',
      ])
      expect(warnSpy).not.toHaveBeenCalled()
    })

    test('ignores invalid URLs and warns once per invalid entry', () => {
      const input =
        'https://example.com, not-a-url, ftp://example.com/file.txt, https://test'

      expect(parseHostnamesFromUrls(input)).toEqual([
        'example.com',
        'example.com',
        'test',
      ])

      expect(warnSpy).toHaveBeenCalledTimes(1)
      expect(warnSpy).toHaveBeenCalledWith(
        'Invalid URL in BASEROW_EXTRA_PUBLIC_URLS: not-a-url'
      )
    })

    test('preserves duplicates and order', () => {
      const input =
        'https://a.example.com, https://a.example.com, https://b.example.com'
      expect(parseHostnamesFromUrls(input)).toEqual([
        'a.example.com',
        'a.example.com',
        'b.example.com',
      ])
    })
  })
})
