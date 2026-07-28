import { TestApp } from '@baserow/test/helpers/testApp'
import {
  encodeUrlWhitespace,
  resolveButtonUrl,
} from '@baserow/modules/database/utils/buttonField'

describe('buttonField utils', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const fields = [{ id: 1, type: 'text', name: 'Slug' }]
  const row = { id: 10, field_1: 'ada' }

  test('resolves field references against the row', () => {
    const field = {
      id: 2,
      type: 'button',
      label: 'Open',
      url_formula: {
        formula: "concat('https://example.com/', get('fields.field_1'))",
        mode: 'simple',
      },
    }
    expect(resolveButtonUrl(testApp._app.$registry, field, row, fields)).toBe(
      'https://example.com/ada'
    )
  })

  test('resolves the URL as the user built it, without encoding', () => {
    const field = {
      id: 2,
      type: 'button',
      label: 'Open',
      url_formula: {
        formula: "concat('https://example.com/item-', get('fields.field_1'))",
        mode: 'simple',
      },
    }
    const spacedRow = { id: 11, field_1: 'Red Button' }
    expect(
      resolveButtonUrl(testApp._app.$registry, field, spacedRow, fields)
    ).toBe('https://example.com/item-Red Button')
  })

  test('lets the formula encode a value that holds reserved characters', () => {
    const field = {
      id: 2,
      type: 'button',
      label: 'Open',
      url_formula: {
        formula:
          "concat('https://example.com/?q=', encode_uri_component(get('fields.field_1')))",
        mode: 'simple',
      },
    }
    const reservedRow = { id: 13, field_1: 'a&b=1' }
    expect(
      resolveButtonUrl(testApp._app.$registry, field, reservedRow, fields)
    ).toBe('https://example.com/?q=a%26b%3D1')
  })

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

  test('returns empty string for empty or broken formulas', () => {
    const empty = { url_formula: { formula: '', mode: 'simple' } }
    const broken = { url_formula: { formula: 'concat(broken', mode: 'simple' } }
    const missingRef = {
      url_formula: { formula: "get('fields.field_99')", mode: 'simple' },
    }
    expect(resolveButtonUrl(testApp._app.$registry, empty, row, fields)).toBe(
      ''
    )
    expect(resolveButtonUrl(testApp._app.$registry, broken, row, fields)).toBe(
      ''
    )
    expect(
      resolveButtonUrl(testApp._app.$registry, missingRef, row, fields)
    ).toBe('')
  })

  test('fails resolution when a referenced field is missing from the context', () => {
    // A missing field (hidden in a public view, or another table in the
    // link-row picker) must not resolve to a partial but valid URL.
    const field = {
      url_formula: {
        formula: "concat('https://example.com/', get('fields.field_99'))",
        mode: 'simple',
      },
    }
    expect(resolveButtonUrl(testApp._app.$registry, field, row, fields)).toBe(
      ''
    )
    expect(resolveButtonUrl(testApp._app.$registry, field, null, fields)).toBe(
      ''
    )
  })

  test('resolves an empty cell to an empty string', () => {
    const field = {
      url_formula: {
        formula: "concat('https://example.com/', get('fields.field_1'))",
        mode: 'simple',
      },
    }
    const emptyRow = { id: 12, field_1: null }
    expect(
      resolveButtonUrl(testApp._app.$registry, field, emptyRow, fields)
    ).toBe('https://example.com/')
  })
})
