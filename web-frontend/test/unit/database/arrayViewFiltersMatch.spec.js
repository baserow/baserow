import { TestApp } from '@baserow/test/helpers/testApp'
import {
  HasValueEqualViewFilterType,
  HasNotValueEqualViewFilterType,
  HasValueContainsViewFilterType,
  HasNotValueContainsViewFilterType,
  HasValueContainsWordViewFilterType,
  HasNotValueContainsWordViewFilterType,
  HasEmptyValueViewFilterType,
  HasNotEmptyValueViewFilterType,
  HasValueLengthIsLowerThanViewFilterType,
  HasAllValuesEqualViewFilterType,
} from '@baserow/modules/database/arrayViewFilters'
import { FormulaFieldType } from '@baserow/modules/database/fieldTypes'
import {
  EmptyViewFilterType,
  NotEmptyViewFilterType,
} from '@baserow/modules/database/viewFilters'

describe('Text-based array view filters', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const hasTextValueEqualCases = [
    {
      cellValue: [],
      filterValue: 'A',
      expected: false,
    },
    {
      cellValue: [{ value: 'B' }, { value: 'A' }],
      filterValue: 'A',
      expected: true,
    },
    {
      cellValue: [{ value: 'a' }],
      filterValue: 'A',
      expected: false,
    },
    {
      cellValue: [{ value: 'Aa' }],
      filterValue: 'A',
      expected: false,
    },
  ]

  const hasValueEqualSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'text',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'char',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'url',
    },
  ]

  describe.each(hasValueEqualSupportedFields)(
    'HasValueEqualViewFilterType %j',
    (field) => {
      test.each(hasTextValueEqualCases)(
        'filter matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasValueEqualViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(testValues.expected)
        }
      )
    }
  )

  describe.each(hasValueEqualSupportedFields)(
    'HasNotValueEqualViewFilterType %j',
    (field) => {
      test.each(hasTextValueEqualCases)(
        'filter not matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasNotValueEqualViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(!testValues.expected)
        }
      )
    }
  )

  const hasValueContainsCases = [
    {
      cellValue: [],
      filterValue: 'A',
      expected: false,
    },
    {
      cellValue: [{ value: 'B' }, { value: 'Aa' }],
      filterValue: 'A',
      expected: true,
    },
    {
      cellValue: [{ value: 't a t' }],
      filterValue: 'A',
      expected: true,
    },
    {
      cellValue: [{ value: 'C' }],
      filterValue: 'A',
      expected: false,
    },
  ]

  const hasValueContainsSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'text',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'char',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'url',
    },
  ]

  describe.each(hasValueContainsSupportedFields)(
    'HasValueContainsViewFilterType %j',
    (field) => {
      test.each(hasValueContainsCases)(
        'filter matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasValueContainsViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(testValues.expected)
        }
      )
    }
  )

  describe.each(hasValueContainsSupportedFields)(
    'HasNotValueContainsViewFilterType %j',
    (field) => {
      test.each(hasValueContainsCases)(
        'filter not matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasNotValueContainsViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(!testValues.expected)
        }
      )
    }
  )

  const hasValueContainsWordCases = [
    {
      cellValue: [],
      filterValue: 'Word',
      expected: false,
    },
    {
      cellValue: [{ value: '...Word...' }, { value: 'Some sentence' }],
      filterValue: 'Word',
      expected: true,
    },
    {
      cellValue: [{ value: 'Word' }],
      filterValue: 'ord',
      expected: false,
    },
    {
      cellValue: [{ value: 'Some word in a sentence.' }],
      filterValue: 'Word',
      expected: true,
    },
    {
      cellValue: [{ value: 'Some Word in a sentence.' }],
      filterValue: 'word',
      expected: true,
    },
  ]

  const hasValueContainsWordSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'text',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'char',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'url',
    },
  ]

  describe.each(hasValueContainsWordSupportedFields)(
    'HasValueContainsWordViewFilterType %j',
    (field) => {
      test.each(hasValueContainsWordCases)(
        'filter matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasValueContainsWordViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(testValues.expected)
        }
      )
    }
  )

  describe.each(hasValueContainsWordSupportedFields)(
    'HasNotValueContainsWordViewFilterType %j',
    (field) => {
      test.each(hasValueContainsWordCases)(
        'filter not matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasNotValueContainsWordViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(!testValues.expected)
        }
      )
    }
  )

  const hasEmptyValueCases = [
    {
      cellValue: [],
      expected: false,
    },
    {
      cellValue: [{ value: 'B' }, { value: '' }],
      expected: true,
    },
    {
      cellValue: [{ value: '' }],
      expected: true,
    },
    {
      cellValue: [{ value: 'C' }],
      expected: false,
    },
  ]

  const hasEmptyValueSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'text',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'char',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'url',
    },
  ]

  describe.each(hasEmptyValueSupportedFields)(
    'HasEmptyValueViewFilterType %j',
    (field) => {
      test.each(hasEmptyValueCases)(
        'filter matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasEmptyValueViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(testValues.expected)
        }
      )
    }
  )

  describe.each(hasEmptyValueSupportedFields)(
    'HasNotEmptyValueViewFilterType %j',
    (field) => {
      test.each(hasEmptyValueCases)(
        'filter not matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasNotEmptyValueViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(!testValues.expected)
        }
      )
    }
  )

  const hasLengthLowerThanValueCases = [
    {
      cellValue: [],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [{ value: 'aaaaa' }, { value: 'aaaaaaaaaa' }],
      filterValue: '6',
      expected: true,
    },
    {
      cellValue: [{ value: 'aaaaa' }],
      filterValue: '5',
      expected: false,
    },
    {
      cellValue: [{ value: '' }],
      filterValue: '1',
      expected: true,
    },
  ]

  const hasLengthLowerThanSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'text',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'char',
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'url',
    },
  ]

  describe.each(hasLengthLowerThanSupportedFields)(
    'HasValueLengthIsLowerThanViewFilterType %j',
    (field) => {
      test.each(hasLengthLowerThanValueCases)(
        'filter matches values %j',
        (testValues) => {
          const fieldType = new field.TestFieldType({
            app: testApp._app,
          })
          const result = new HasValueLengthIsLowerThanViewFilterType({
            app: testApp._app,
          }).matches(
            testValues.cellValue,
            testValues.filterValue,
            field,
            fieldType
          )
          expect(result).toBe(testValues.expected)
        }
      )
    }
  )
})

describe('bool-based array view filters', () => {
  let testApp = null
  let fieldType = null

  const fieldDefinition = {
    type: 'lookup',
    formula_type: 'array',
    array_formula_type: 'boolean  ',
  }

  beforeAll(() => {
    testApp = new TestApp()
    fieldType = new FormulaFieldType({
      app: testApp._app,
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const notEmptyBoolValueCases = [
    {
      cellValue: [],
      expected: true,
    },
    {
      cellValue: [{ value: 'true' }, { value: 'true' }, { value: false }],
      expected: false,
    },
    {
      cellValue: [{ value: '' }],
      expected: false,
    },
    {
      cellValue: [{ value: 'C' }],
      expected: false,
    },
  ]

  test.each(notEmptyBoolValueCases)(
    'hasNotEmptyBoolValueCases %j',
    (testValues) => {
      const fieldType = new FormulaFieldType({
        app: testApp._app,
      })
      const result = new NotEmptyViewFilterType({
        app: testApp._app,
      }).matches(testValues.cellValue, null, fieldDefinition, fieldType)
      expect(result).toBe(!testValues.expected)
    }
  )

  test.each(notEmptyBoolValueCases)(
    'hasEmptyBoolValueCases %j',
    (testValues) => {
      const result = new EmptyViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(testValues.expected)
    }
  )

  const hasAnyValueBoolCases = [
    {
      cellValue: [],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: true,
      expected: true,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: false,
      expected: true,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      filterValue: false,
      expected: true,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: false,
      expected: true,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: '' }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: '' }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: false,
      expected: false,
    },
  ]

  test.each(hasAnyValueBoolCases)('hasAnyValueBoolCases %j', (testValues) => {
    const result = new HasValueEqualViewFilterType({
      app: testApp._app,
    }).matches(
      testValues.cellValue,
      testValues.filterValue,
      fieldDefinition,
      fieldType
    )
    expect(result).toBe(testValues.expected)
  })

  const hasNotValueBoolCases = [
    {
      cellValue: [],
      filterValue: true,
      expected: true,
    },
    {
      cellValue: [],
      filterValue: false,
      expected: true,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: false,
      expected: true,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: true,
      expected: true,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: false,
      expected: true,
    },
    {
      cellValue: [{ value: false }],
      filterValue: true,
      expected: true,
    },
    {
      cellValue: [{ value: false }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: true,
      expected: true,
    },
    {
      cellValue: [{ value: '' }],
      filterValue: true,
      expected: true,
    },
    {
      cellValue: [{ value: '' }],
      filterValue: false,
      expected: true,
    },
  ]

  test.each(hasNotValueBoolCases)('hasNotValueBoolCases %j', (testValues) => {
    const result = new HasNotValueEqualViewFilterType({
      app: testApp._app,
    }).matches(
      testValues.cellValue,
      testValues.filterValue,
      fieldDefinition,
      fieldType
    )
    expect(result).toBe(testValues.expected)
  })

  const hasAllValueBoolCases = [
    {
      cellValue: [],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: true,
      expected: true,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: 'XYZ' }],
      filterValue: false,
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      filterValue: false,
      expected: true,
    },
    {
      cellValue: [{ value: '' }],
      filterValue: true,
      expected: false,
    },
    {
      cellValue: [{ value: '' }],
      filterValue: false,
      expected: false,
    },
  ]

  test.each(hasAllValueBoolCases)('hasAllValueBoolCases %j', (testValues) => {
    const result = new HasAllValuesEqualViewFilterType({
      app: testApp._app,
    }).matches(
      testValues.cellValue,
      testValues.filterValue,
      fieldDefinition,
      fieldType
    )
    expect(result).toBe(testValues.expected)
  })
})
