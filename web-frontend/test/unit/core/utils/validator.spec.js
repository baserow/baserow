import {
  ensureArray,
  ensureDateTime,
  ensureInteger,
  ensureString,
  ensureStringOrInteger,
} from '@baserow/modules/core/utils/validator'
import { expect } from '@jest/globals'
import { DATE_FORMATS } from '@baserow/modules/builder/enums'

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

describe('ensureDateTime', () => {
  it('should raise an error for empty values', () => {
    const error = new Error(`Value is not a valid date`)
    expect(() => ensureDateTime(null)).toThrow(error)
    expect(() => ensureDateTime('')).toThrow(error)
    expect(() => ensureDateTime({})).toThrow(error)
    expect(() => ensureDateTime([])).toThrow(error)
  })

  it('should convert the value to a date if valid', () => {
    // In JavaScript Date objects month are 0 indexed, so month 0 is January
    const date = new Date(2024, 3, 25).toISOString()
    expect(
      ensureDateTime('2024-04-25', DATE_FORMATS.ISO.format).toISOString()
    ).toBe(date)
    expect(
      ensureDateTime('25/04/2024', DATE_FORMATS.EU.format).toISOString()
    ).toBe(date)
    expect(
      ensureDateTime('04/25/2024', DATE_FORMATS.US.format).toISOString()
    ).toBe(date)
  })
})
