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
})
