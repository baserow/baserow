import {
  ensureArray,
  ensureDateTime,
  ensureInteger,
  ensureString,
  ensureNumeric,
  ensureStringOrInteger,
  ensurePositiveInteger,
  ensureDate,
} from '@baserow/modules/core/utils/validator'
import { expect } from '@jest/globals'
import { QUERY_PARAM_TYPE_HANDLER_FUNCTIONS } from '@baserow/modules/builder/enums'
import { DateOnly } from '@baserow/modules/core/utils/date'

describe('ensureInteger', () => {
  it('should return the value as an integer if it is already an integer', () => {
    expect(ensureInteger(5)).toBe(5)
    expect(ensureInteger(-10)).toBe(-10)
  })

  it('should convert a string representation of an integer to an integer', () => {
    expect(ensureInteger('15')).toBe(15)
    expect(ensureInteger('-20')).toBe(-20)
  })

  it('should throw an error if the value is not a valid integer', () => {
    expect(() => ensureInteger('abc')).toThrow(Error)
    expect(() => ensureInteger('12.34')).toThrow(Error)
    expect(() => ensureInteger(true)).toThrow(Error)
    expect(() => ensureInteger(null)).toThrow(Error)
    expect(() => ensureInteger([])).toThrow(Error)
  })
})

describe('ensurePositiveInteger', () => {
  // Valid positive integers
  test('returns the same value for positive integers', () => {
    expect(ensurePositiveInteger(5)).toBe(5)
    expect(ensurePositiveInteger(0)).toBe(0)
    expect(ensurePositiveInteger(1000)).toBe(1000)
  })

  // String conversions
  test('converts string representations of positive integers', () => {
    expect(ensurePositiveInteger('42')).toBe(42)
    expect(ensurePositiveInteger('0')).toBe(0)
    expect(ensurePositiveInteger('+123')).toBe(123)
  })

  // Null handling
  test('returns null when value is null and allowNull is true', () => {
    expect(ensurePositiveInteger(null, { allowNull: true })).toBeNull()
  })

  test('returns null when value is empty string and allowNull is true', () => {
    expect(ensurePositiveInteger('', { allowNull: true })).toBeNull()
  })

  // Error cases
  test('throws error for negative integers', () => {
    expect(() => ensurePositiveInteger(-5)).toThrow(
      'Value is not a positive integer.'
    )
    expect(() => ensurePositiveInteger('-10')).toThrow(
      'Value is not a positive integer.'
    )
  })

  test('throws error for non-integer values', () => {
    expect(() => ensurePositiveInteger('abc')).toThrow('not a valid integer')
    expect(() => ensurePositiveInteger({})).toThrow('not a valid integer')
    expect(() => ensurePositiveInteger([])).toThrow('not a valid integer')
    expect(() => ensurePositiveInteger(3.14)).toThrow('not a valid integer')
    expect(() => ensurePositiveInteger('3.14')).toThrow('not a valid integer')
  })

  test('throws error for null when allowNull is false', () => {
    expect(() => ensurePositiveInteger(null)).toThrow('not a valid integer')
  })

  test('throws error for empty string when allowNull is false', () => {
    expect(() => ensurePositiveInteger('')).toThrow('not a valid integer')
  })

  // Default behavior
  test('allowNull defaults to false', () => {
    expect(() => ensurePositiveInteger(null)).toThrow()
    expect(() => ensurePositiveInteger('')).toThrow()
  })
})

describe('ensureNumeric', () => {
  // Test valid numeric inputs
  test('returns the same value for valid numbers', () => {
    expect(ensureNumeric(42)).toBe(42)
    expect(ensureNumeric(0)).toBe(0)
    expect(ensureNumeric(-10)).toBe(-10)
    expect(ensureNumeric(3.14)).toBe(3.14)
  })

  // Test string conversion
  test('converts valid numeric strings to numbers', () => {
    expect(ensureNumeric('42')).toBe(42)
    expect(ensureNumeric('0')).toBe(0)
    expect(ensureNumeric('-10')).toBe(-10)
    expect(ensureNumeric('3.14')).toBe(3.14)
    expect(ensureNumeric('+42')).toBe(42)
  })

  // Test null handling
  test('handles null values based on allowNull option', () => {
    expect(() => ensureNumeric(null)).toThrow()
    expect(() => ensureNumeric(undefined)).toThrow()
    expect(ensureNumeric(null, { allowNull: true })).toBeNull()
    expect(ensureNumeric(undefined, { allowNull: true })).toBeNull()
  })

  // Test empty string handling
  test('handles empty strings based on allowNull option', () => {
    expect(() => ensureNumeric('')).toThrow()
    expect(ensureNumeric('', { allowNull: true })).toBeNull()
  })

  // Test invalid inputs
  test('throws error for non-numeric strings', () => {
    expect(() => ensureNumeric('abc')).toThrow()
    expect(() => ensureNumeric('123abc')).toThrow()
    expect(() => ensureNumeric('abc123')).toThrow()
    expect(() => ensureNumeric('12.34.56')).toThrow()
    expect(() => ensureNumeric('Infinity')).toThrow()
    expect(() => ensureNumeric('-Infinity')).toThrow()
  })

  test('throws error for objects and arrays', () => {
    expect(() => ensureNumeric({})).toThrow()
    expect(() => ensureNumeric([])).toThrow()
    expect(() => ensureNumeric([1, 2, 3])).toThrow()
  })

  test('throws error for boolean values', () => {
    expect(() => ensureNumeric(true)).toThrow()
    expect(() => ensureNumeric(false)).toThrow()
  })

  test('throws error for undefined', () => {
    expect(() => ensureNumeric(undefined)).toThrow()
  })

  // Test error message
  test('provides descriptive error message', () => {
    try {
      ensureNumeric('not-a-number')
    } catch (error) {
      expect(error.message).toContain('not-a-number')
      expect(error.message).toContain('not a valid number')
    }
  })
})

describe('ensureString', () => {
  it('should return an empty string if the value is falsy', () => {
    expect(ensureString(null)).toBe('')
    expect(ensureString(undefined)).toBe('')
    expect(ensureString('')).toBe('')
    expect(ensureString([])).toBe('')
    expect(ensureString({})).toBe('')
  })

  it('should convert the value to a string if it is truthy', () => {
    expect(ensureString(5)).toBe('5')
    expect(ensureString(true)).toBe('true')
    expect(ensureString(0)).toBe('0')
    expect(ensureString(false)).toBe('false')
    expect(ensureString([1, 2, 3])).toBe('1,2,3')
    expect(ensureString({ key: 'value' })).toBe('{"key":"value"}')
    expect(ensureString(['foo', ['bar']])).toBe('foo,bar')
    expect(ensureString(['foo', { bar: 'baz' }, 'a', ['b']])).toBe(
      'foo,{"bar":"baz"},a,b'
    )
    expect(ensureString({ foo: ['a', 'b'], baz: { d: ['e', 'f'] } })).toBe(
      '{"foo":["a","b"],"baz":{"d":["e","f"]}}'
    )
  })
  it('should convert dates', () => {
    expect(ensureString('2025-07-03')).toBe('2025-07-03')
    expect(ensureString('2025-07-09T22:00:00Z')).toBe('2025-07-09 22:00:00')
    expect(ensureString(new Date('2025-07-09T22:00:00Z'))).toBe(
      '2025-07-09 22:00:00'
    )
    expect(ensureString(new DateOnly('2025-07-09'))).toBe('2025-07-09')
    expect(ensureString(new DateOnly(NaN))).toBe('Invalid Date')
    expect(ensureString(new Date(NaN))).toBe('Invalid Date')
  })
})

describe('ensureStringOrInteger', () => {
  it('should return the same value if value is an integer', () => {
    expect(ensureStringOrInteger(0)).toBe(0)
    expect(ensureStringOrInteger(1)).toBe(1)
    expect(ensureStringOrInteger(10)).toBe(10)
  })

  it('should return the same value if value is a string', () => {
    expect(ensureStringOrInteger('0')).toBe('0')
    expect(ensureStringOrInteger('1')).toBe('1')
    expect(ensureStringOrInteger('10')).toBe('10')
  })

  it('should return an empty string if value is falsey and allowEmpty is true', () => {
    expect(ensureStringOrInteger('', { allowEmpty: true })).toBe('')
    expect(ensureStringOrInteger([], { allowEmpty: true })).toBe('')
    expect(ensureStringOrInteger(null, { allowEmpty: true })).toBe('')
    expect(ensureStringOrInteger(undefined, { allowEmpty: true })).toBe('')
  })

  it('should return an error if value is falsey and allowEmpty is false', () => {
    const error = new Error('A valid String is required.')
    expect(() => ensureStringOrInteger('', { allowEmpty: false })).toThrow(
      error
    )
    expect(() => ensureStringOrInteger([], { allowEmpty: false })).toThrow(
      error
    )
    expect(() => ensureStringOrInteger(null, { allowEmpty: false })).toThrow(
      error
    )
    expect(() =>
      ensureStringOrInteger(undefined, { allowEmpty: false })
    ).toThrow(error)
  })
})

describe('ensureArray', () => {
  it('should return an empty array if the value is falsy', () => {
    expect(ensureArray(null)).toStrictEqual([])
    expect(ensureArray('')).toStrictEqual([])
    expect(ensureArray([])).toStrictEqual([])
    expect(ensureArray([[[]]])).toStrictEqual([[[]]])
  })
  it('should raise an error for empty values when allowEmpty is not set', () => {
    const error = new Error('A non empty value is required.')
    expect(() => ensureArray(null, { allowEmpty: false })).toThrow(error)
    expect(() => ensureArray('', { allowEmpty: false })).toThrow(error)
    expect(() => ensureArray([], { allowEmpty: false })).toThrow(error)
  })
  it('should convert the value to an array if it is truthy', () => {
    expect(ensureArray(5)).toStrictEqual([5])
    expect(ensureArray(true)).toStrictEqual([true])
    expect(ensureArray(0)).toStrictEqual([0])
    expect(ensureArray(false)).toStrictEqual([false])
    expect(ensureArray('one,two,three')).toStrictEqual(['one', 'two', 'three'])
    expect(ensureArray('one,two,,')).toStrictEqual(['one', 'two', '', ''])
    expect(ensureArray([1, 2, 3])).toStrictEqual([1, 2, 3])
    expect(ensureArray({ key: 'value' })).toStrictEqual([{ key: 'value' }])
  })
})

describe('ensurePositiveInteger', () => {
  it('should return the value as a positive integer if it is already a positive integer', () => {
    expect(ensurePositiveInteger(5)).toBe(5)
    expect(ensurePositiveInteger(0)).toBe(0)
    expect(ensurePositiveInteger(1000)).toBe(1000)
  })

  it('should convert a string representation of a positive integer', () => {
    expect(ensurePositiveInteger('15')).toBe(15)
    expect(ensurePositiveInteger('0')).toBe(0)
    expect(ensurePositiveInteger('1000')).toBe(1000)
  })

  it('should throw an error for negative integers', () => {
    expect(() => ensurePositiveInteger(-1)).toThrow(
      'Value is not a positive integer.'
    )
    expect(() => ensurePositiveInteger('-5')).toThrow(
      'Value is not a positive integer.'
    )
  })

  it('should throw an error for non-integer values', () => {
    expect(() => ensurePositiveInteger('abc')).toThrow(
      "Value 'abc' is not a valid integer or convertible to an integer."
    )
    expect(() => ensurePositiveInteger('12.34')).toThrow(
      "Value '12.34' is not a valid integer or convertible to an integer."
    )
    expect(() => ensurePositiveInteger(true)).toThrow(
      "Value 'true' is not a valid integer or convertible to an integer."
    )
    expect(() => ensurePositiveInteger([])).toThrow(
      "Value '' is not a valid integer or convertible to an integer."
    )
  })

  it('should handle null values according to options', () => {
    expect(() => ensurePositiveInteger(null)).toThrow(
      "Value 'null' is not a valid integer or convertible to an integer."
    )
    expect(ensurePositiveInteger(null, { allowNull: true })).toBe(null)
  })
})

describe('QUERY_PARAM_TYPE_HANDLER_FUNCTIONS', () => {
  describe('numeric handler', () => {
    const numericHandler = QUERY_PARAM_TYPE_HANDLER_FUNCTIONS.numeric

    it('should return null for empty input', () => {
      expect(numericHandler('')).toBe(null)
      expect(numericHandler(null)).toBe(null)
      expect(numericHandler(undefined)).toBe(null)
    })

    it('should handle single numeric string', () => {
      expect(numericHandler('5')).toBe(5)
      expect(numericHandler('42')).toBe(42)
      expect(numericHandler('1.5')).toBe(1.5)
      expect(numericHandler('-1')).toBe(-1)
    })

    it('should handle comma-separated numeric strings', () => {
      expect(numericHandler('1,2,3')).toEqual([1, 2, 3])
      expect(numericHandler('42,123')).toEqual([42, 123])
    })

    it('should filter out invalid values from arrays', () => {
      expect(numericHandler('1,2,')).toEqual([1, 2, null])
      expect(numericHandler('1,2')).toEqual([1, 2])
      expect(numericHandler(',1,2')).toEqual([null, 1, 2])
      expect(numericHandler('1,,2')).toEqual([1, null, 2])
    })

    it('should throw error for invalid numeric values', () => {
      expect(() => numericHandler('1,abc,3')).toThrow()
    })
  })

  describe('text handler', () => {
    const textHandler = QUERY_PARAM_TYPE_HANDLER_FUNCTIONS.text

    it('should return null for empty input', () => {
      expect(textHandler('')).toBe(null)
      expect(textHandler(null)).toBe(null)
      expect(textHandler(undefined)).toBe(null)
    })

    it('should handle single text value', () => {
      expect(textHandler('hello')).toBe('hello')
      expect(textHandler('test123')).toBe('test123')
    })

    it('should handle comma-separated text values', () => {
      expect(textHandler('hello,world')).toEqual(['hello', 'world'])
      expect(textHandler('a,b,c')).toEqual(['a', 'b', 'c'])
    })

    it('should filter out empty values from arrays', () => {
      expect(textHandler('test,')).toEqual(['test', ''])
      expect(textHandler('test,,value')).toEqual(['test', '', 'value'])
    })

    it('should handle numeric values as strings', () => {
      expect(textHandler('123')).toBe('123')
      expect(textHandler('test,123,abc')).toEqual(['test', '123', 'abc'])
    })
  })
})

describe('ensureDate', () => {
  describe('with allowEmpty = true (default)', () => {
    test('returns null for null value', () => {
      const result = ensureDate(null)
      expect(result).toBeNull()
    })

    test('returns null for undefined value', () => {
      const result = ensureDate(undefined)
      expect(result).toBeNull()
    })

    test('returns null for empty string', () => {
      const result = ensureDate('')
      expect(result).toBeNull()
    })

    test('returns DateOnly for valid date string', () => {
      const result = ensureDate('2023-12-01')
      expect(result).toBeInstanceOf(DateOnly)
      expect(result.getFullYear()).toBe(2023)
    })

    test('returns DateOnly for Date object', () => {
      const date = new Date('2023-12-01')
      const result = ensureDate(date)
      expect(result).toBeInstanceOf(DateOnly)
    })

    test('throws TypeError for invalid date string', () => {
      expect(() => ensureDate('invalid-date')).toThrow(TypeError)
      expect(() => ensureDate('invalid-date')).toThrow(
        'Value is not a valid date or convertible to a date.'
      )
    })

    test('throws TypeError for non-date values', () => {
      expect(() => ensureDate(123)).toThrow(TypeError)
      expect(() => ensureDate({})).toThrow(TypeError)
      expect(() => ensureDate([])).toThrow(TypeError)
    })
  })

  describe('with allowEmpty = false', () => {
    test('throws Error for null value', () => {
      expect(() => ensureDate(null, { allowEmpty: false })).toThrow(Error)
      expect(() => ensureDate(null, { allowEmpty: false })).toThrow(
        'A non empty value is required.'
      )
    })

    test('throws Error for undefined value', () => {
      expect(() => ensureDate(undefined, { allowEmpty: false })).toThrow(Error)
      expect(() => ensureDate(undefined, { allowEmpty: false })).toThrow(
        'A non empty value is required.'
      )
    })

    test('throws Error for empty string', () => {
      expect(() => ensureDate('', { allowEmpty: false })).toThrow(Error)
      expect(() => ensureDate('', { allowEmpty: false })).toThrow(
        'A non empty value is required.'
      )
    })

    test('returns DateOnly for valid date', () => {
      const result = ensureDate('2023-12-01', { allowEmpty: false })
      expect(result).toBeInstanceOf(DateOnly)
    })
  })
})

describe('ensureDateTime', () => {
  describe('with allowEmpty = true (default)', () => {
    test('returns null for null value', () => {
      const result = ensureDateTime(null)
      expect(result).toBeNull()
    })

    test('returns null for undefined value', () => {
      const result = ensureDateTime(undefined)
      expect(result).toBeNull()
    })

    test('returns null for empty string', () => {
      const result = ensureDateTime('')
      expect(result).toBeNull()
    })

    test('returns same Date object when value is already a Date', () => {
      const date = new Date('2023-12-01T10:30:00Z')
      const result = ensureDateTime(date)
      expect(result).toBe(date)
    })

    test('returns Date for valid ISO string with default format', () => {
      const result = ensureDateTime('2023-12-01T10:30:00Z')
      expect(result).toBeInstanceOf(Date)
      expect(result.getUTCFullYear()).toBe(2023)
      expect(result.getUTCMonth()).toBe(11)
      expect(result.getUTCDate()).toBe(1)
      expect(result.getUTCHours()).toBe(10)
      expect(result.getUTCMinutes()).toBe(30)
    })

    test('returns Date for valid string with custom format', () => {
      const result = ensureDateTime('01/12/2023 10:30', {
        format: 'DD/MM/YYYY HH:mm',
      })
      expect(result).toBeInstanceOf(Date)
      expect(result.getUTCDate()).toBe(1)
      expect(result.getUTCMonth()).toBe(11)
    })

    test('throws TypeError for invalid date string with default format', () => {
      expect(() => ensureDateTime('invalid-date')).toThrow(TypeError)
      expect(() => ensureDateTime('invalid-date')).toThrow(
        'Value is not a valid datetime or convertible to a datetime.'
      )
    })

    test('throws TypeError for invalid date string with custom format', () => {
      expect(() =>
        ensureDateTime('2023-12-01', { format: 'DD/MM/YYYY' })
      ).toThrow(TypeError)
    })
  })

  describe('with allowEmpty = false', () => {
    test('throws Error for null value', () => {
      expect(() => ensureDateTime(null, { allowEmpty: false })).toThrow(Error)
      expect(() => ensureDateTime(null, { allowEmpty: false })).toThrow(
        'A non empty value is required.'
      )
    })

    test('throws Error for undefined value', () => {
      expect(() => ensureDateTime(undefined, { allowEmpty: false })).toThrow(
        Error
      )
      expect(() => ensureDateTime(undefined, { allowEmpty: false })).toThrow(
        'A non empty value is required.'
      )
    })

    test('throws Error for empty string', () => {
      expect(() => ensureDateTime('', { allowEmpty: false })).toThrow(Error)
      expect(() => ensureDateTime('', { allowEmpty: false })).toThrow(
        'A non empty value is required.'
      )
    })

    test('returns Date for valid datetime', () => {
      const result = ensureDateTime('2023-12-01T10:30:00Z', {
        allowEmpty: false,
      })
      expect(result).toBeInstanceOf(Date)
    })
  })

  describe('with custom format', () => {
    test('parses date with DD/MM/YYYY format', () => {
      const result = ensureDateTime('15/03/2023', { format: 'DD/MM/YYYY' })
      expect(result.getUTCDate()).toBe(15)
      expect(result.getUTCMonth()).toBe(2) // March is month 2
      expect(result.getUTCFullYear()).toBe(2023)
    })

    test('parses datetime with custom format', () => {
      const result = ensureDateTime('2023-12-01 14:30:45', {
        format: 'YYYY-MM-DD HH:mm:ss',
      })
      expect(result.getUTCHours()).toBe(14)
      expect(result.getUTCMinutes()).toBe(30)
      expect(result.getUTCSeconds()).toBe(45)
    })
  })
})
