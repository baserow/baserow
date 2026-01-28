import {
  VALID_FORMULA_VALIDATION_TESTS,
  INVALID_FORMULA_VALIDATION_TESTS,
} from '@baserow_test_cases/formula_visitor_cases'
import { TestApp } from '@baserow/test/helpers/testApp'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { isFormulaValid } from '@baserow/modules/core/formula'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'

class TestDataProviderType extends DataProviderType {
  static getType() {
    return 'test_data_provider'
  }
}

describe('BaserowFormulaValidationVisitor', () => {
  let testApp = null
  let validationContext = null
  let functions = null

  beforeAll(() => {
    testApp = new TestApp()
    const dataProviderRegistry = [new TestDataProviderType()]
    validationContext = { dataProviderRegistry }
    functions = new RuntimeFunctionCollection(testApp.store.$registry)
  })

  test.each(VALID_FORMULA_VALIDATION_TESTS)(
    'should correctly validate the formula %s',
    ({ formula }) => {
      const result = isFormulaValid(
        formula,
        functions,
        false,
        validationContext
      )
      expect(result).toMatchObject({ valid: true, errors: [] })
    }
  )

  test.each(INVALID_FORMULA_VALIDATION_TESTS)(
    'should be flagged as an invalid formula: %s',
    ({ formula, frontendError }) => {
      const result = isFormulaValid(
        formula,
        functions,
        false,
        validationContext
      )
      if (frontendError) {
        expect(result).toMatchObject({ valid: false, errors: [frontendError] })
      } else {
        expect(result.valid).toBe(false)
      }
    }
  )
})
