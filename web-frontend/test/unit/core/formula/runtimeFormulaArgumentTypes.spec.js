import { expect } from 'vitest'
import {
  BaserowRuntimeFormulaArgumentType,
  TimezoneBaserowRuntimeFormulaArgumentType,
  ThousandSeparatorBaserowRuntimeFormulaArgumentType,
  DecimalSeparatorBaserowRuntimeFormulaArgumentType,
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
