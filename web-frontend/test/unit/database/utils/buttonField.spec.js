import {
  encodeUrlWhitespace,
  urlWithAllowedProtocol,
} from '@baserow/modules/database/utils/buttonField'

describe('buttonField utils', () => {
  test('encodeUrlWhitespace only touches whitespace', () => {
    // Encoding more would mangle the URL structure the formula builds, and
    // double-encode what `encode_uri_component()` already escaped.
    expect(encodeUrlWhitespace('https://example.com/Red Button')).toBe(
      'https://example.com/Red%20Button'
    )
    expect(encodeUrlWhitespace('https://example.com/?q=a%26b&x=1#top')).toBe(
      'https://example.com/?q=a%26b&x=1#top'
    )
  })

  test('urlWithAllowedProtocol keeps allowed and relative URLs', () => {
    expect(urlWithAllowedProtocol('https://example.com')).toBe(
      'https://example.com'
    )
    expect(urlWithAllowedProtocol('mailto:ada@example.com')).toBe(
      'mailto:ada@example.com'
    )
    expect(urlWithAllowedProtocol('/rows/1')).toBe('/rows/1')
  })

  test('urlWithAllowedProtocol drops a disallowed protocol', () => {
    expect(urlWithAllowedProtocol('javascript:alert(1)')).toBe('')
    expect(urlWithAllowedProtocol('JavaScript:alert(1)')).toBe('')
    expect(urlWithAllowedProtocol('data:text/html,<script>')).toBe('')
  })

  test('urlWithAllowedProtocol drops a protocol hidden behind C0 controls', () => {
    // These control characters are not whitespace, so neither `trim()` nor
    // `encodeUrlWhitespace` removes them, but the browser's URL parser strips
    // them before deciding the protocol. A row value can hold any of them.
    for (const control of ['\u0001', '\u0008', '\u000e', '\u001f']) {
      expect(urlWithAllowedProtocol(`${control}javascript:alert(1)`)).toBe('')
      expect(
        urlWithAllowedProtocol(`${control}${control}javascript:alert(1)`)
      ).toBe('')
    }
    // A tab anywhere in the URL is removed by the same parser.
    expect(urlWithAllowedProtocol('java\tscript:alert(1)')).toBe('')
  })

  test('urlWithAllowedProtocol still passes an ordinary relative URL', () => {
    expect(urlWithAllowedProtocol('/rows/1')).toBe('/rows/1')
    expect(urlWithAllowedProtocol('rows/1?q=a%20b#top')).toBe(
      'rows/1?q=a%20b#top'
    )
  })
})
