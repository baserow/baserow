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

  const hasSelectOptionsEqualCases = [
    {
      cellValue: [],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [
        { value: { id: 2, value: 'B' } },
        { value: { id: 1, value: 'A' } },
      ],
      filterValue: '1',
      expected: true,
    },
    {
      cellValue: [{ value: { id: 1, value: 'A' } }],
      filterValue: '2',
      expected: false,
    },
    {
      cellValue: [{ value: { id: 3, value: 'Aa' } }],
      filterValue: '1',
      expected: false,
    },
  ]

  const hasSelectOptionEqualSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'single_select',
    },
  ]

  describe.each(hasSelectOptionEqualSupportedFields)(
    'HasValueEqualViewFilterType %j',
    (field) => {
      test.each(hasSelectOptionsEqualCases)(
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

  describe.each(hasSelectOptionEqualSupportedFields)(
    'HasNotValueEqualViewFilterType %j',
    (field) => {
      test.each(hasSelectOptionsEqualCases)(
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

  const hasSelectOptionContainsCases = [
    {
      cellValue: [],
      filterValue: 'A',
      expected: false,
    },
    {
      cellValue: [
        { value: { id: 2, value: 'B' } },
        { value: { id: 1, value: 'A' } },
      ],
      filterValue: 'A',
      expected: true,
    },
    {
      cellValue: [{ value: { id: 1, value: 'A' } }],
      filterValue: 'B',
      expected: false,
    },
    {
      cellValue: [{ value: { id: 3, value: 'Aa' } }],
      filterValue: 'a',
      expected: true,
    },
  ]

  const hasSelectOptionContainsSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'single_select',
    },
  ]

  describe.each(hasSelectOptionContainsSupportedFields)(
    'HasValueContainsViewFilterType %j',
    (field) => {
      test.each(hasSelectOptionContainsCases)(
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

  describe.each(hasSelectOptionContainsSupportedFields)(
    'HasNotValueContainsViewFilterType %j',
    (field) => {
      test.each(hasSelectOptionContainsCases)(
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

  const hasSelectOptionContainsWordCases = [
    {
      cellValue: [],
      filterValue: 'A',
      expected: false,
    },
    {
      cellValue: [
        { value: { id: 2, value: 'B' } },
        { value: { id: 1, value: 'Aa' } },
      ],
      filterValue: 'Aa',
      expected: true,
    },
    {
      cellValue: [{ value: { id: 1, value: 'A' } }],
      filterValue: 'B',
      expected: false,
    },
    {
      cellValue: [{ value: { id: 3, value: 'Aa' } }],
      filterValue: 'a',
      expected: false,
    },
  ]

  const hasSelectOptionsContainsWordSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'single_select',
    },
  ]

  describe.each(hasSelectOptionsContainsWordSupportedFields)(
    'HasValueContainsWordViewFilterType %j',
    (field) => {
      test.each(hasSelectOptionContainsWordCases)(
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

  describe.each(hasSelectOptionsContainsWordSupportedFields)(
    'HasNotValueContainsWordViewFilterType %j',
    (field) => {
      test.each(hasSelectOptionContainsWordCases)(
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

  const hasEmptySelectOptionsCases = [
    {
      cellValue: [],
      expected: false,
    },
    {
      cellValue: [{ value: { id: 1, value: 'a' } }, { value: null }],
      expected: true,
    },
    {
      cellValue: [{ value: null }],
      expected: true,
    },
    {
      cellValue: [{ value: { id: 2, value: 'b' } }],
      expected: false,
    },
  ]

  const hasEmptySelectOptionSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'single_select',
    },
  ]

  describe.each(hasEmptySelectOptionSupportedFields)(
    'HasEmptyValueViewFilterType %j',
    (field) => {
      test.each(hasEmptySelectOptionsCases)(
        'filter not matches values %j',
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

  describe.each(hasEmptySelectOptionSupportedFields)(
    'HasNotEmptyValueViewFilterType %j',
    (field) => {
      test.each(hasEmptySelectOptionsCases)(
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
})

describe('Boolean-based array view filters', () => {
  let testApp = null
  let fieldType = null

  const fieldDefinition = {
    type: 'lookup',
    formula_type: 'array',
    array_formula_type: 'boolean',
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

  const isEmptyBoolValueCases = [
    {
      cellValue: [],
      expected: true,
    },
    {
      cellValue: [{ value: true }, { value: false }],
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      expected: false,
    },
    {
      cellValue: [{ value: true }],
      expected: false,
    },
  ]

  test.each(isEmptyBoolValueCases)('isEmptyBoolValueCases %j', (testValues) => {
    const result = new NotEmptyViewFilterType({
      app: testApp._app,
    }).matches(testValues.cellValue, null, fieldDefinition, fieldType)
    expect(result).toBe(!testValues.expected)
  })

  test.each(isEmptyBoolValueCases)(
    'isNotEmptyBoolValueCases %j',
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
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [],
      filterValue: '0',
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: '1',
      expected: true,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: '0',
      expected: true,
    },
    {
      cellValue: [{ value: false }],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      filterValue: '0',
      expected: true,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: '0',
      expected: true,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: '1',
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
      filterValue: '1',
      expected: true,
    },
    {
      cellValue: [],
      filterValue: '0',
      expected: true,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: '0',
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: '0',
      expected: true,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      filterValue: '1',
      expected: true,
    },
    {
      cellValue: [{ value: false }],
      filterValue: '0',
      expected: false,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: '0',
      expected: false,
    },
    {
      cellValue: [{ value: false }, { value: false }],
      filterValue: '1',
      expected: true,
    },
  ]

  test.each(hasNotValueBoolCases)(
    'hasNotValueEqualBoolCases %j',
    (testValues) => {
      const result = new HasNotValueEqualViewFilterType({
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

  const hasAllValueBooleanCases = [
    {
      cellValue: [],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [],
      filterValue: '0',
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: false }],
      filterValue: '0',
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: '0',
      expected: false,
    },
    {
      cellValue: [{ value: true }, { value: true }, { value: true }],
      filterValue: '1',
      expected: true,
    },
    {
      cellValue: [{ value: false }],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [{ value: false }],
      filterValue: '0',
      expected: true,
    },
  ]

  test.each(hasAllValueBooleanCases)(
    'hasAllValueBooleanCases %j',
    (testValues) => {
      const result = new HasAllValuesEqualViewFilterType({
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
})
