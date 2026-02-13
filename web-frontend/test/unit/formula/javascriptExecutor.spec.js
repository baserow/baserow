import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import JavascriptExecutor from '@baserow/modules/core/formula/parser/javascriptExecutor'
import {
  VALID_FORMULA_TESTS,
  INVALID_FORMULA_TESTS,
} from '@baserow_test_cases/formula_runtime_cases'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('JavascriptExecutor', () => {
  let testApp = null
  beforeEach(() => {
    testApp = new TestApp()
  })

  test.each(VALID_FORMULA_TESTS)(
    'should correctly resolve the formula %s',
    ({ formula, result, context }) => {
      const tree = parseBaserowFormula(formula)
      expect(
        new JavascriptExecutor(
          {
            get(name) {
              return testApp.store.$registry.get('runtimeFormulaFunction', name)
            },
          },
          context
        ).visit(tree)
      ).toEqual(result)
    }
  )

  test.each(INVALID_FORMULA_TESTS)(
    'should correctly raise an error for formula %s',
    ({ formula, context }) => {
      const tree = parseBaserowFormula(formula)
      expect(() =>
        new JavascriptExecutor(
          {
            get(name) {
              return testApp.store.$registry.get('runtimeFormulaFunction', name)
            },
          },
          context
        ).visit(tree)
      ).toThrow()
    }
  )
})
