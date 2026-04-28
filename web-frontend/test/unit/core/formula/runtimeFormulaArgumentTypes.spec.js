import { expect } from 'vitest'
import {
  BaserowRuntimeFormulaArgumentType,
  TimezoneBaserowRuntimeFormulaArgumentType,
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
