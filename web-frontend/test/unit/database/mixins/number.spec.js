/**
 * @jest-environment jsdom
 */

import {
  formatNumberValue,
  parseNumberValue,
} from '@baserow/modules/database/utils/number'

describe('test number formatting and parsing', () => {
  const baseField = {
    number_decimal_places: 2,
    number_negative: true,
    number_prefix: '',
    number_suffix: '',
    number_separator: '',
  }

  test('test basic number formatting', () => {
    const field = { ...baseField }
    expect(formatNumberValue(field, 1234.56)).toBe('1234.56')
    expect(formatNumberValue(field, -1234.56)).toBe('-1234.56')
    expect(formatNumberValue(field, null)).toBe('')
    expect(formatNumberValue(field, '')).toBe('')
    expect(formatNumberValue(field, '1234.56789')).toBe('1234.57')
  })

  test('test number formatting with different separators', () => {
    const field = { ...baseField }
    field.number_separator = 'SPACE_COMMA'
    expect(formatNumberValue(field, 1234.56)).toBe('1 234,56')
    expect(formatNumberValue(field, -1000000.99)).toBe('-1 000 000,99')

    field.number_separator = 'PERIOD_COMMA'
    expect(formatNumberValue(field, 1234.56)).toBe('1.234,56')
    expect(formatNumberValue(field, -1000000.99)).toBe('-1.000.000,99')

    field.number_separator = 'SPACE_PERIOD'
    expect(formatNumberValue(field, 1234.56)).toBe('1 234.56')
    expect(formatNumberValue(field, -1000000.99)).toBe('-1 000 000.99')

    field.number_separator = 'COMMA_PERIOD'
    expect(formatNumberValue(field, 1234.56)).toBe('1,234.56')
    expect(formatNumberValue(field, -1000000.99)).toBe('-1,000,000.99')
  })

  test('test number formatting with prefix and suffix', () => {
    const field = { ...baseField }
    field.number_prefix = '$'
    expect(formatNumberValue(field, 1234.56)).toBe('$1234.56')
    expect(formatNumberValue(field, -1234.56)).toBe('-$1234.56')

    field.number_suffix = ' USD'
    expect(formatNumberValue(field, 1234.56)).toBe('$1234.56 USD')
    expect(formatNumberValue(field, -1234.56)).toBe('-$1234.56 USD')

    field.number_prefix = '$'
    field.number_suffix = ' USD'
    expect(formatNumberValue(field, 1234.56)).toBe('$1234.56 USD')
    expect(formatNumberValue(field, -1234.56)).toBe('-$1234.56 USD')

    field.number_separator = 'SPACE_COMMA'
    field.number_prefix = '$'
    field.number_suffix = ' USD'
    expect(formatNumberValue(field, 1234.56)).toBe('$1 234,56 USD')
    expect(formatNumberValue(field, -1234.56)).toBe('-$1 234,56 USD')
  })

  test('test number formatting with different decimal places', () => {
    const field = { ...baseField }
    field.number_decimal_places = 0
    field.number_separator = 'SPACE_COMMA'
    field.number_prefix = '$'
    field.number_suffix = ' USD'
    expect(formatNumberValue(field, 1234.56)).toBe('$1 235 USD')

    field.number_decimal_places = 3
    expect(formatNumberValue(field, 1234.56)).toBe('$1 234,560 USD')
  })

  test('test number parsing with different formats', () => {
    const field = { ...baseField }
    expect(parseNumberValue(field, null)).toBe(null)
    expect(parseNumberValue(field, '')).toBe(null)

    field.number_separator = 'SPACE_COMMA'
    expect(parseNumberValue(field, '1 234,56').toNumber()).toBe(1234.56)
    expect(parseNumberValue(field, '-1 234,56').toNumber()).toBe(-1234.56)

    field.number_separator = 'PERIOD_COMMA'
    expect(parseNumberValue(field, '1.234,56').toNumber()).toBe(1234.56)
    expect(parseNumberValue(field, '-1.234,56').toNumber()).toBe(-1234.56)

    field.number_separator = 'SPACE_PERIOD'
    expect(parseNumberValue(field, '1 234.56').toNumber()).toBe(1234.56)
    expect(parseNumberValue(field, '-1 234.56').toNumber()).toBe(-1234.56)

    field.number_separator = 'COMMA_PERIOD'
    expect(parseNumberValue(field, '1,234.56').toNumber()).toBe(1234.56)
    expect(parseNumberValue(field, '-1,234.56').toNumber()).toBe(-1234.56)
  })

  test('test number parsing with prefix and suffix', () => {
    const field = { ...baseField }
    field.number_separator = 'PERIOD_COMMA'

    field.number_prefix = '$'
    expect(parseNumberValue(field, '$1.234,56').toNumber()).toBe(1234.56)
    expect(parseNumberValue(field, '-$1.234,56').toNumber()).toBe(-1234.56)

    field.number_suffix = ' USD'
    expect(parseNumberValue(field, '$1.234,56 USD').toNumber()).toBe(1234.56)
    expect(parseNumberValue(field, '-$1.234,56 USD').toNumber()).toBe(-1234.56)

    field.number_prefix = ''
    expect(parseNumberValue(field, '1.234,56 USD').toNumber()).toBe(1234.56)
    expect(parseNumberValue(field, '-1.234,56 USD').toNumber()).toBe(-1234.56)
  })
})
