import { expect } from 'vitest'
import {
  BaserowRuntimeFormulaArgumentType,
  DatetimeFormatBaserowRuntimeFormulaArgumentType,
  TimezoneBaserowRuntimeFormulaArgumentType,
  ThousandSeparatorBaserowRuntimeFormulaArgumentType,
  DecimalSeparatorBaserowRuntimeFormulaArgumentType,
  DurationBaserowRuntimeFormulaArgumentType,
  Timedelta,
} from '@baserow/modules/core/runtimeFormulaArgumentTypes'

describe('BaserowRuntimeFormulaArgumentType', () => {
  test('getErrorMessage returns null by default', () => {
    const argType = new BaserowRuntimeFormulaArgumentType()
    expect(argType.getErrorMessage('foo', {})).toBeNull()
  })
})

describe('TimezoneBaserowRuntimeFormulaArgumentType', () => {
  test('getErrorMessage returns a human-readable message for invalid timezone', () => {
    const argType = new TimezoneBaserowRuntimeFormulaArgumentType()
    const mocki18n = {
      t: (key, params) => `'${params.value}' is not a valid timezone.`,
    }
    const message = argType.getErrorMessage('Europe/Foo', mocki18n)
    expect(message).toContain("'Europe/Foo' is not a valid timezone.")
  })
})

describe('ThousandSeparatorBaserowRuntimeFormulaArgumentType', () => {
  test.each([
    { value: ',', expected: true },
    { value: '.', expected: true },
    { value: ' ', expected: true },
    { value: '', expected: true },
    { value: ';', expected: false },
    { value: '|', expected: false },
    { value: 1, expected: false },
    { value: null, expected: false },
  ])('returns $expected for $value', ({ value, expected }) => {
    expect(
      new ThousandSeparatorBaserowRuntimeFormulaArgumentType().test(value)
    ).toBe(expected)
  })

  test('getErrorMessage returns a human-readable message', () => {
    const argType = new ThousandSeparatorBaserowRuntimeFormulaArgumentType()
    const mocki18n = {
      t: (key, params) =>
        `'${params.value}' is not a valid thousand separator.`,
    }
    const message = argType.getErrorMessage(';', mocki18n)
    expect(message).toContain("';' is not a valid thousand separator.")
  })
})

describe('DecimalSeparatorBaserowRuntimeFormulaArgumentType', () => {
  test.each([
    { value: ',', expected: true },
    { value: '.', expected: true },
    { value: ' ', expected: false },
    { value: '', expected: false },
    { value: ';', expected: false },
    { value: 1, expected: false },
    { value: null, expected: false },
  ])('returns $expected for $value', ({ value, expected }) => {
    expect(
      new DecimalSeparatorBaserowRuntimeFormulaArgumentType().test(value)
    ).toBe(expected)
  })

  test('getErrorMessage returns a human-readable message', () => {
    const argType = new DecimalSeparatorBaserowRuntimeFormulaArgumentType()
    const mocki18n = {
      t: (key, params) => `'${params.value}' is not a valid decimal separator.`,
    }
    const message = argType.getErrorMessage(';', mocki18n)
    expect(message).toContain("';' is not a valid decimal separator.")
  })
})

describe('DurationBaserowRuntimeFormulaArgumentType', () => {
  test.each([
    { value: '1 day', expected: true },
    { value: '2 days', expected: true },
    { value: '3 weeks', expected: true },
    { value: '4 hours', expected: true },
    { value: '30 minutes', expected: true },
    { value: '45 seconds', expected: true },
    { value: '1 year', expected: true },
    { value: '1 month', expected: true },
    { value: new Timedelta(86400000), expected: true },
    { value: '-1 day', expected: false },
    { value: 'foo', expected: false },
    { value: '', expected: false },
    { value: '1', expected: true },
    { value: 1, expected: true },
    { value: null, expected: false },
  ])('returns $expected for "$value"', ({ value, expected }) => {
    expect(new DurationBaserowRuntimeFormulaArgumentType().test(value)).toBe(
      expected
    )
  })

  test.each([
    { value: '1 day', expected: new Timedelta(86400000) },
    { value: '2 days', expected: new Timedelta(2 * 86400000) },
    { value: '3 weeks', expected: new Timedelta(3 * 7 * 86400000) },
    { value: '4 hours', expected: new Timedelta(4 * 3600000) },
    { value: '30 minutes', expected: new Timedelta(30 * 60000) },
    { value: '45 seconds', expected: new Timedelta(45 * 1000) },
  ])('parse converts "$value" to Timedelta', ({ value, expected }) => {
    expect(
      new DurationBaserowRuntimeFormulaArgumentType().parse(value)
    ).toStrictEqual(expected)
  })

  test('getErrorMessage returns a human-readable message', () => {
    const argType = new DurationBaserowRuntimeFormulaArgumentType()
    const mocki18n = {
      t: (key, params) => `'${params.value}' is not a valid duration string.`,
    }
    const message = argType.getErrorMessage('not valid', mocki18n)
    expect(message).toContain("'not valid' is not a valid duration string.")
  })
})

describe('DatetimeFormatBaserowRuntimeFormulaArgumentType', () => {
  test.each([
    { value: 'YYYY-MM-DD', expected: true },
    { value: 'DD/MM/YYYY', expected: true },
    { value: 'YYYY-MM-DD HH:mm:ss', expected: true },
    { value: 'DD/MM/YYYY HH:mm:ss', expected: true },
    { value: 'HH:mm:ss', expected: true },
    { value: 'SSS', expected: true },
    { value: '', expected: false },
    { value: 'SS', expected: false },
    { value: 'S', expected: false },
    { value: 'Z', expected: false },
    { value: 'YYYY-MM-DD HH:mm:SS', expected: false },
    { value: 123, expected: false },
    { value: null, expected: false },
  ])('test() returns $expected for "$value"', ({ value, expected }) => {
    expect(
      new DatetimeFormatBaserowRuntimeFormulaArgumentType().test(value)
    ).toBe(expected)
  })

  test('getErrorMessage returns a human-readable message', () => {
    const argType = new DatetimeFormatBaserowRuntimeFormulaArgumentType()
    const mocki18n = {
      t: (key, params) => `'${params.value}' is not a valid datetime format.`,
    }
    const message = argType.getErrorMessage('SS', mocki18n)
    expect(message).toContain("'SS' is not a valid datetime format.")
  })
})
