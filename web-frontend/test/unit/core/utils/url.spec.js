import { isRelativeUrl } from '@baserow/modules/core/utils/url.js'
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
})
