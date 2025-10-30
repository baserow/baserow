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
  HasValueHigherThanViewFilterType,
  HasValueHigherThanOrEqualViewFilterType,
  HasNotValueHigherThanViewFilterType,
  HasNotValueHigherThanOrEqualViewFilterType,
  HasDateBeforeViewFilterType,
  HasNotDateBeforeViewFilterType,
  HasDateEqualViewFilterType,
  HasNotDateEqualViewFilterType,
  HasDateAfterViewFilterType,
  HasNotDateAfterViewFilterType,
  HasDateOnOrBeforeViewFilterType,
  HasNotDateOnOrBeforeViewFilterType,
  HasDateOnOrAfterViewFilterType,
  HasNotDateOnOrAfterViewFilterType,
  HasDateWithinViewFilterType,
  HasValueLowerThanViewFilterType,
  HasNotValueLowerThanViewFilterType,
} from '@baserow/modules/database/arrayViewFilters'
import {
  FormulaFieldType,
  LookupFieldType,
} from '@baserow/modules/database/fieldTypes'
import {
  EmptyViewFilterType,
  NotEmptyViewFilterType,
} from '@baserow/modules/database/viewFilters'
import {
  dateBeforeCases,
  dateEqualCases,
  dateAfterCases,
  dateBeforeOrEqualCases,
  dateAfterOrEqualCases,
  dateWithinDaysAgo,
  dateWithinDays,
  dateWithinWeeks,
  dateWithinMonths,
} from './viewFiltersMatch.spec.js'

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
          expect(result).toBe(
            testValues.filterValue === '' || !testValues.expected
          )
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

describe('Number-based array view filters', () => {
  let testApp = null
  let fieldType = null

  const fieldDefinition = {
    type: 'lookup',
    formula_type: 'array',
    array_formula_type: 'number',
  }

  beforeAll(() => {
    testApp = new TestApp()
    fieldType = new LookupFieldType({
      app: testApp._app,
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const hasEmptyValueTestCases = [
    {
      cellValue: [],
      filterValue: '',
      expected: false,
    },
    {
      cellValue: [{ value: null }],
      filterValue: '',
      expected: true,
    },
    {
      cellValue: [{ value: '123.0' }, { value: null }],
      filterValue: '',
      expected: true,
    },
    {
      cellValue: [{ value: '123.0' }, { value: '' }],
      filterValue: '',
      expected: true,
    },
  ]

  const hasValueContainsTestCases = [
    {
      cellValue: [],
      filterValue: '',
      expected: { has: true, hasNot: true },
    },
    {
      cellValue: [{ value: null }],
      filterValue: '',
      expected: { has: true, hasNot: true },
    },
    {
      cellValue: [{ value: '' }],
      filterValue: '',
      expected: { has: true, hasNot: true },
    },
    {
      cellValue: [{ value: 123.0 }, { value: null }],
      filterValue: '123',
      expected: { has: true, hasNot: false },
    },
    {
      cellValue: [{ value: '123.0' }, { value: null }],
      filterValue: '123',
      expected: { has: true, hasNot: false },
    },
    {
      cellValue: [{ value: 123.0 }, { value: '' }],
      filterValue: '100',
      expected: { has: false, hasNot: true },
    },
    {
      cellValue: [{ value: 1.11101 }],
      filterValue: '10',
      expected: { has: true, hasNot: false },
    },
    {
      cellValue: [{ value: '1.11101' }],
      filterValue: '10',
      expected: { has: true, hasNot: false },
    },
    {
      cellValue: [{ value: 10100.001 }],
      filterValue: '20',
      expected: { has: false, hasNot: true },
    },
  ]

  // has value higher/lower are implemented with a code path that will return
  // true for empty filterValues. This requires per filter type result check
  const hasValueHigherThanOrEqualTestCases = [
    {
      cellValue: [],
      filterValue: '',
      expected: {
        higher: true,
        higherEqual: true,
        notHigher: true,
        notHigherEqual: true,
      },
    },
    {
      cellValue: [{ value: null }],
      filterValue: '',
      expected: {
        higher: true,
        higherEqual: true,
        notHigher: true,
        notHigherEqual: true,
      },
    },
    {
      cellValue: [{ value: '' }],
      filterValue: '',
      expected: {
        higher: true,
        higherEqual: true,
        notHigher: true,
        notHigherEqual: true,
      },
    },
    {
      cellValue: [{ value: null }],
      filterValue: 10,
      expected: {
        higher: false,
        higherEqual: false,
        notHigher: true,
        notHigherEqual: true,
      },
    },
    {
      cellValue: [{ value: null }],
      filterValue: 10,
      expected: {
        higher: false,
        higherEqual: false,
        notHigher: true,
        notHigherEqual: true,
      },
    },
    {
      cellValue: [{ value: 123.0 }, { value: null }],
      filterValue: '123',
      expected: {
        higher: false,
        higherEqual: true,
        notHigher: true,
        notHigherEqual: false,
      },
    },

    {
      cellValue: [{ value: '123.0' }, { value: null }],
      filterValue: '123',
      expected: {
        higher: false,
        higherEqual: true,
        notHigher: true,
        notHigherEqual: false,
      },
    },

    {
      cellValue: [{ value: 123.0 }],
      filterValue: '123.0001',
      expected: {
        higher: false,
        higherEqual: false,
        notHigher: true,
        notHigherEqual: true,
      },
    },
    {
      cellValue: [{ value: '123.0' }],
      filterValue: '123.0001',
      expected: {
        higher: false,
        higherEqual: false,
        notHigher: true,
        notHigherEqual: true,
      },
    },
    {
      cellValue: [{ value: 123.0 }, { value: 500 }],
      filterValue: '123.0001',
      expected: {
        higher: true,
        higherEqual: true,
        notHigher: false,
        notHigherEqual: false,
      },
    },
  ]

  test.each(hasEmptyValueTestCases)(
    'hasEmptyValueTestCases %j',
    (testValues) => {
      const result = new HasEmptyValueViewFilterType({
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

  test.each(hasEmptyValueTestCases)(
    'hasNotEmptyValueTestCases %j',
    (testValues) => {
      const result = new HasNotEmptyValueViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(!testValues.expected)
    }
  )

  test.each(hasValueContainsTestCases)(
    'hasValueContainsTestCases %j',
    (testValues) => {
      const result = new HasValueContainsViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(testValues.expected.has)
    }
  )

  test.each(hasValueContainsTestCases)(
    'hasNotValueContainsTestCases %j',
    (testValues) => {
      const result = new HasNotValueContainsViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(testValues.expected.hasNot)
    }
  )

  test.each(hasValueHigherThanOrEqualTestCases)(
    'hasValueHigherTestCases %j',
    (testValues) => {
      const result = new HasValueHigherThanViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(testValues.expected.higher)
    }
  )

  test.each(hasValueHigherThanOrEqualTestCases)(
    'hasValueHigherOrEqualTestCases %j',
    (testValues) => {
      const result = new HasValueHigherThanOrEqualViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(testValues.expected.higherEqual)
    }
  )

  test.each(hasValueHigherThanOrEqualTestCases)(
    'hasNotValueHigherTestCases %j',
    (testValues) => {
      const result = new HasNotValueHigherThanViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(testValues.expected.notHigher)
    }
  )

  test.each(hasValueHigherThanOrEqualTestCases)(
    'hasNotValueHigherOrEqualTestCases %j',
    (testValues) => {
      const result = new HasNotValueHigherThanOrEqualViewFilterType({
        app: testApp._app,
      }).matches(
        testValues.cellValue,
        testValues.filterValue,
        fieldDefinition,
        fieldType
      )
      expect(result).toBe(testValues.expected.notHigherEqual)
    }
  )
})

describe('Multiple select-based array view filters', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const hasMultipleSelectOptionsEqualCases = [
    {
      cellValue: [],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [
        {
          value: [
            { id: 2, value: 'B' },
            { id: 3, value: 'C' },
          ],
        },
        { value: [{ id: 1, value: 'A' }] },
      ],
      filterValue: '1',
      expected: true,
    },
    {
      cellValue: [
        {
          value: [
            { id: 1, value: 'A' },
            { id: 3, value: 'C' },
          ],
        },
      ],
      filterValue: '2',
      expected: false,
    },
    {
      cellValue: [{ value: [{ id: 4, value: 'Aa' }] }],
      filterValue: '1',
      expected: false,
    },
    {
      cellValue: [{ value: [{ id: 4, value: 'Aa' }] }],
      filterValue: '',
      expected: true,
    },
    {
      cellValue: [
        {
          value: [
            { id: 2, value: 'B' },
            { id: 3, value: 'C' },
          ],
        },
        { value: [{ id: 1, value: 'A' }] },
      ],
      filterValue: '2,3',
      expected: true,
    },
    {
      cellValue: [
        {
          value: [
            { id: 2, value: 'B' },
            { id: 3, value: 'C' },
          ],
        },
        { value: [{ id: 1, value: 'A' }] },
      ],
      filterValue: '2',
      expected: false,
    },
  ]

  const hasMultipleSelectOptionEqualSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'multiple_select',
    },
  ]

  describe.each(hasMultipleSelectOptionEqualSupportedFields)(
    'HasValueEqualViewFilterType %j',
    (field) => {
      test.each(hasMultipleSelectOptionsEqualCases)(
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

  describe.each(hasMultipleSelectOptionEqualSupportedFields)(
    'HasNotValueEqualViewFilterType %j',
    (field) => {
      test.each(hasMultipleSelectOptionsEqualCases)(
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
          expect(result).toBe(
            testValues.filterValue === '' || !testValues.expected
          )
        }
      )
    }
  )

  const hasMultipleSelectOptionContainsCases = [
    {
      cellValue: [],
      filterValue: 'A',
      expected: false,
    },
    {
      cellValue: [
        { value: [{ id: 2, value: 'B' }] },
        {
          value: [
            { id: 1, value: 'A' },
            { id: 2, value: 'B' },
          ],
        },
      ],
      filterValue: 'A',
      expected: true,
    },
    {
      cellValue: [
        {
          value: [
            { id: 1, value: 'A' },
            { id: 2, value: 'C' },
          ],
        },
      ],
      filterValue: 'B',
      expected: false,
    },
    {
      cellValue: [{ value: [{ id: 3, value: 'Aa' }] }],
      filterValue: 'a',
      expected: true,
    },
    {
      cellValue: [{ value: [{ id: 3, value: 'a' }] }],
      filterValue: '',
      expected: true,
    },
  ]

  const hasMultipleSelectOptionContainsSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'multiple_select',
    },
  ]

  describe.each(hasMultipleSelectOptionContainsSupportedFields)(
    'HasValueContainsViewFilterType %j',
    (field) => {
      test.each(hasMultipleSelectOptionContainsCases)(
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

  describe.each(hasMultipleSelectOptionContainsSupportedFields)(
    'HasNotValueContainsViewFilterType %j',
    (field) => {
      test.each(hasMultipleSelectOptionContainsCases)(
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
          expect(result).toBe(
            testValues.filterValue === '' || !testValues.expected
          )
        }
      )
    }
  )

  const hasMultipleSelectOptionContainsWordCases = [
    {
      cellValue: [],
      filterValue: 'A',
      expected: false,
    },
    {
      cellValue: [
        {
          value: [
            { id: 2, value: 'B' },
            { id: 3, value: 'C' },
          ],
        },
        { value: [{ id: 1, value: 'Aa' }] },
        { value: [] },
      ],
      filterValue: 'Aa',
      expected: true,
    },
    {
      cellValue: [{ value: [{ id: 1, value: 'A' }] }],
      filterValue: 'B',
      expected: false,
    },
    {
      cellValue: [{ value: [{ id: 3, value: 'Aa' }] }],
      filterValue: 'a',
      expected: false,
    },
    {
      cellValue: [{ value: [{ id: 1, value: 'A' }] }],
      filterValue: '',
      expected: true,
    },
  ]

  const hasMultipleSelectOptionsContainsWordSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'multiple_select',
    },
  ]

  describe.each(hasMultipleSelectOptionsContainsWordSupportedFields)(
    'HasValueContainsWordViewFilterType %j',
    (field) => {
      test.each(hasMultipleSelectOptionContainsWordCases)(
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

  describe.each(hasMultipleSelectOptionsContainsWordSupportedFields)(
    'HasNotValueContainsWordViewFilterType %j',
    (field) => {
      test.each(hasMultipleSelectOptionContainsWordCases)(
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
          expect(result).toBe(
            testValues.filterValue === '' || !testValues.expected
          )
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
      cellValue: [{ value: [{ id: 1, value: 'a' }] }, { value: [] }],
      expected: true,
    },
    {
      cellValue: [{ value: [] }],
      expected: true,
    },
    {
      cellValue: [{ value: [{ id: 2, value: 'b' }] }],
      expected: false,
    },
  ]

  const hasEmptySelectOptionSupportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'multiple_select',
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

describe('Date array view filters', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const supportedFields = [
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'date',
      date_include_time: false,
    },
    {
      TestFieldType: FormulaFieldType,
      formula_type: 'array',
      array_formula_type: 'date',
      date_include_time: true,
    },
  ]

  const hasEmptyValueCases = [
    {
      cellValue: [],
      expected: false,
    },
    {
      cellValue: [{ value: null }],
      expected: true,
    },
    {
      cellValue: [{ value: '2021-01-01' }, { value: null }],
      expected: true,
    },
    {
      cellValue: [{ value: '2021-01-01' }, { value: '2021-01-02' }],
      expected: false,
    },
  ]

  describe.each(supportedFields)('HasEmptyValueViewFilterType %j', (field) => {
    test.each(hasEmptyValueCases)('filter matches values %j', (testValues) => {
      const fieldType = new field.TestFieldType({
        app: testApp._app,
      })
      const result = new HasEmptyValueViewFilterType({
        app: testApp._app,
      }).matches(testValues.cellValue, testValues.filterValue, field, fieldType)
      expect(result).toBe(testValues.expected)
    })
  })

  describe.each(supportedFields)(
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

  const hasValueContainsCases = [
    {
      cellValue: [],
      filterValue: '19',
      expected: false,
    },
    {
      cellValue: [{ value: '2020-01-01' }, { value: '2019-01-02' }],
      filterValue: '19',
      expected: true,
    },
    {
      cellValue: [{ value: '2021-01-01' }, { value: '2021-01-02' }],
      filterValue: '3',
      expected: false,
    },
    {
      cellValue: [{ value: '2021-01-01' }, { value: '2021-01-02' }],
      filterValue: '2',
      expected: true,
    },
  ]

  describe.each(supportedFields)(
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

  describe.each(supportedFields)(
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

  test.each(dateBeforeCases)('HasDateBeforeViewFilterType', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasDateBeforeViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateBeforeCases)('HasNotDateBeforeViewFilterType', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasNotDateBeforeViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(!values.expected)
  })

  test.each(dateBeforeOrEqualCases)(
    'HasDateOnOrBeforeViewFilterType',
    (values) => {
      const rowValue = [{ value: values.rowValue }]
      const result = new HasDateOnOrBeforeViewFilterType({
        app: testApp,
      }).matches(rowValue, `${values.filterValue}?exact_date`, {
        date_include_time: true,
      })
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateBeforeOrEqualCases)(
    'HasNotDateOnOrBeforeViewFilterType',
    (values) => {
      const rowValue = [{ value: values.rowValue }]
      const result = new HasNotDateOnOrBeforeViewFilterType({
        app: testApp,
      }).matches(rowValue, `${values.filterValue}?exact_date`, {
        date_include_time: true,
      })
      expect(result).toBe(!values.expected)
    }
  )

  test.each(dateEqualCases)('HasDateEqualViewFilterType', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasDateEqualViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateEqualCases)('HasNotDateEqualViewFilterType', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasNotDateEqualViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(!values.expected)
  })

  test.each(dateAfterCases)('HasDateAfterViewFilterType', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasDateAfterViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(values.expected)
  })

  test.each(dateAfterCases)('HaNotDateAfterViewFilterType', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasNotDateAfterViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?exact_date`, {
      date_include_time: true,
    })
    expect(result).toBe(!values.expected)
  })

  test.each(dateAfterOrEqualCases)(
    'HasDateOnOrAfterViewFilterType',
    (values) => {
      const rowValue = [{ value: values.rowValue }]
      const result = new HasDateOnOrAfterViewFilterType({
        app: testApp,
      }).matches(rowValue, `${values.filterValue}?exact_date`, {
        date_include_time: true,
      })
      expect(result).toBe(values.expected)
    }
  )

  test.each(dateAfterOrEqualCases)(
    'HasNoeDateOnOrAfterViewFilterType',
    (values) => {
      const rowValue = [{ value: values.rowValue }]
      const result = new HasNotDateOnOrAfterViewFilterType({
        app: testApp,
      }).matches(rowValue, `${values.filterValue}?exact_date`, {
        date_include_time: true,
      })
      expect(result).toBe(!values.expected)
    }
  )

  test.each(dateWithinDaysAgo)('HasDateWithinDaysAgo', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasDateWithinViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?nr_days_ago`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinDays)('HasDateWithinDays', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasDateWithinViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?nr_days_from_now`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinWeeks)('HasDateWithinWeeks', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasDateWithinViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?nr_weeks_from_now`, {})
    expect(result).toBe(values.expected)
  })

  test.each(dateWithinMonths)('HasDateWithinMonths', (values) => {
    const rowValue = [{ value: values.rowValue }]
    const result = new HasDateWithinViewFilterType({
      app: testApp,
    }).matches(rowValue, `${values.filterValue}?nr_months_from_now`, {})
    expect(result).toBe(values.expected)
  })
})

describe('Empty / not Empty array view filters', () => {
  let testApp = null
  let fieldType = null

  const testCases = [
    {
      fieldDefinition: {
        type: 'lookup',
        formula_type: 'array',
        array_formula_type: 'text',
      },
      values: [
        {
          cellValue: [],
          expected: true,
        },
        {
          cellValue: [{ value: '' }],
          expected: true,
        },
      ],
    },
    {
      fieldDefinition: {
        type: 'lookup',
        formula_type: 'array',
        array_formula_type: 'number',
      },
      values: [
        {
          cellValue: [],
          expected: true,
        },
        {
          cellValue: [{ value: 3 }],
          expected: false,
        },
      ],
    },
    {
      fieldDefinition: {
        type: 'lookup',
        formula_type: 'array',
        array_formula_type: 'date',
      },
      values: [
        {
          cellValue: [],
          expected: true,
        },
        {
          cellValue: [{ value: '10/01/21' }],
          expected: false,
        },
      ],
    },
    {
      fieldDefinition: {
        type: 'lookup',
        formula_type: 'array',
        array_formula_type: 'single_select',
      },
      values: [
        {
          cellValue: [],
          expected: true,
        },
        {
          cellValue: [{ value: { id: 1, value: 'a' } }],
          expected: false,
        },
      ],
    },
    {
      fieldDefinition: {
        type: 'lookup',
        formula_type: 'array',
        array_formula_type: 'multiple_select',
      },
      values: [
        {
          cellValue: [],
          expected: true,
        },
        {
          cellValue: [{ value: [{ id: 1, value: 'a' }] }],
          expected: false,
        },
      ],
    },
  ]

  beforeAll(() => {
    testApp = new TestApp()
    fieldType = new FormulaFieldType({
      app: testApp._app,
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test.each(testCases)('isEmptyCases %j', (testCase) => {
    const fieldDefinition = testCase.fieldDefinition
    testCase.values.forEach((testValues) => {
      const result = new EmptyViewFilterType({
        app: testApp._app,
      }).matches(testValues.cellValue, null, fieldDefinition, fieldType)
      expect(result).toBe(testValues.expected)
    })
  })

  test.each(testCases)('isNotEmptyCases %j', (testCase) => {
    const fieldDefinition = testCase.fieldDefinition
    testCase.values.forEach((testValues) => {
      const result = new NotEmptyViewFilterType({
        app: testApp._app,
      }).matches(testValues.cellValue, null, fieldDefinition, fieldType)
      expect(result).toBe(!testValues.expected)
    })
  })
})

const MultipleCollaboratorsEmptyCases = [
  {
    filterType: 'empty',
    rowValue: [],
    expected: true,
  },
  {
    filterType: 'empty',
    rowValue: [{ id: 1, value: [] }],
    expected: true,
  },
  {
    filterType: 'empty',
    rowValue: [{ id: 2, value: [{ id: 1, name: 'foo' }] }],
    expected: false,
  },
  {
    filterType: 'empty',
    rowValue: [
      { id: 2, value: [{ id: 1, name: 'foo' }] },
      { id: 1, value: [] },
    ],
    expected: false,
  },
]

const MultipleCollaboratorsArrayFiltersCases = [
  {
    rowValue: [],
    filterValue: {
      hasValueEqual: '1',
      hasValueContains: 'fo',
      hasValueContainsWord: 'foo',
    },
    // expected is false, because there's no empty value in the list
    expected: {
      hasEmptyValue: false,
      hasValueEqual: false,
      hasValueContains: false,
      hasValueContainsWord: false,
    },
  },
  {
    rowValue: [{ id: 1, value: [] }],
    filterValue: {
      hasValueEqual: '1',
      hasValueContains: 'fo',
      hasValueContainsWord: 'foo',
    },
    expected: {
      hasEmptyValue: true,
      hasValueEqual: false,
      hasValueContains: false,
      hasValueContainsWord: false,
    },
  },
  {
    rowValue: [
      {
        id: 2,
        value: [
          { id: 1, name: 'foo' },
          { id: 2, name: 'bar' },
        ],
      },
      { id: 3, value: [{ id: 2, name: 'bar' }] },
    ],
    filterValue: {
      hasValueEqual: '1',
      hasValueContains: 'fo',
      hasValueContainsWord: 'foo',
    },
    expected: {
      hasEmptyValue: false,
      hasValueEqual: true,
      hasValueContains: true,
      hasValueContainsWord: true,
    },
  },
  {
    rowValue: [
      { id: 2, value: [{ id: 1, name: 'foo' }] },
      { id: 1, value: [] },
    ],
    filterValue: {
      hasValueEqual: '2',
      hasValueContains: 'fo',
      hasValueContainsWord: 'foo',
    },
    expected: {
      hasEmptyValue: true,
      hasValueEqual: false,
      hasValueContains: true,
      hasValueContainsWord: true,
    },
  },

  {
    rowValue: [
      {
        id: 2,
        value: [
          { id: 1, name: 'foo' },
          { id: 2, name: 'bar' },
        ],
      },
      { id: 3, value: [{ id: 2, name: 'bar' }] },
    ],
    filterValue: {
      hasValueEqual: '100',
      hasValueContains: 'za',
      hasValueContainsWord: 'zap!',
    },
    expected: {
      hasEmptyValue: false,
      hasValueEqual: false,
      hasValueContains: false,
      hasValueContainsWord: false,
    },
  },
]

describe('Multiple collaborators view filters', () => {
  let testApp = null
  let fieldType = null
  const field = {
    type: 'lookup',
    formula_type: 'array',
    array_formula_type: 'multiple_collaborators',
  }

  beforeAll(() => {
    testApp = new TestApp()
    fieldType = new FormulaFieldType({ app: testApp.getApp() })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test.each(MultipleCollaboratorsEmptyCases)(
    'Multiple collaborators is empty.',
    (values) => {
      const result = new EmptyViewFilterType({
        app: testApp.getApp(),
      }).matches(values.rowValue, '', field, fieldType)
      expect(result).toBe(values.expected)
    }
  )

  test.each(MultipleCollaboratorsEmptyCases)(
    'Multiple collaborators is not empty.',
    (values) => {
      const result = new NotEmptyViewFilterType({
        app: testApp.getApp(),
      }).matches(values.rowValue, '', field, fieldType)
      expect(result).toBe(!values.expected)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has empty value empty %j.',
    (values) => {
      const result = new HasEmptyValueViewFilterType({
        app: testApp.getApp(),
      }).matches(values.rowValue, '', field, fieldType)
      expect(result).toBe(values.expected.hasEmptyValue)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has not empty value empty %j.',
    (values) => {
      const result = new HasNotEmptyValueViewFilterType({
        app: testApp.getApp(),
      }).matches(values.rowValue, '', field, fieldType)
      expect(result).toBe(!values.expected.hasEmptyValue)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has value equal %j.',
    (values) => {
      const result = new HasValueEqualViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueEqual,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasValueEqual)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has not value equal %j.',
    (values) => {
      const result = new HasNotValueEqualViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueEqual,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasValueEqual)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has value contains %j.',
    (values) => {
      const result = new HasValueContainsViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueContains,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasValueContains)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has not value contains %j.',
    (values) => {
      const result = new HasNotValueContainsViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueContains,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasValueContains)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has value contains word %j.',
    (values) => {
      const result = new HasValueContainsWordViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueContainsWord,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasValueContainsWord)
    }
  )

  test.each(MultipleCollaboratorsArrayFiltersCases)(
    'Multiple collaborators has not value contains word %j.',
    (values) => {
      const result = new HasNotValueContainsWordViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueContainsWord,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasValueContainsWord)
    }
  )
})

const durationEmptyCases = [
  {
    cellValue: [],
    expected: true,
  },
  {
    cellValue: [{ value: 1 }],
    expected: false,
  },
  {
    cellValue: [{ value: null }],
    expected: true,
  },
  {
    cellValue: [{ value: '1' }, { value: null }],
    expected: false,
  },
]

describe('Duration view filters', () => {
  let testApp = null

  beforeAll(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test.each(durationEmptyCases)('Duration is empty %j', (testValues) => {
    const fieldType = new FormulaFieldType({ app: testApp })
    const field = {
      type: 'lookup',
      formula_type: 'array',
      array_formula_type: 'duration',
    }
    const result = new EmptyViewFilterType({
      app: testApp,
    }).matches(testValues.cellValue, '', field, fieldType)
    expect(result).toBe(testValues.expected)
  })

  test.each(durationEmptyCases)('Duration is not empty %j', (testValues) => {
    const fieldType = new FormulaFieldType({ app: testApp })
    const field = {
      type: 'lookup',
      formula_type: 'array',
      array_formula_type: 'duration',
    }
    const result = new NotEmptyViewFilterType({
      app: testApp,
    }).matches(testValues.cellValue, '', field, fieldType)
    expect(result).toBe(!testValues.expected)
  })
})

describe('Duration lookup filters', () => {
  let testApp = null
  let fieldType = null
  const field = {
    type: 'lookup',
    formula_type: 'array',
    array_formula_type: 'duration',
  }

  beforeAll(() => {
    testApp = new TestApp()
    fieldType = new FormulaFieldType({ app: testApp.getApp() })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  const DurationLookupFilterCases = [
    {
      rowValue: [],
      filterValue: {
        hasEmptyValue: '',
        hasValueEqual: '86400',
        hasValueLower: '86400',
        hasValueLowerOrEqual: '86400',
        hasValueHigher: '86400',
        hasValueHigherOrEqual: '86400',
      },

      expected: {
        hasEmptyValue: false,
        hasValueEqual: false,
        hasValueLower: false,
        hasValueLowerOrEqual: false,
        hasValueHigher: false,
        hasValueHigherOrEqual: false,
      },
    },
    {
      rowValue: [{ id: 1, value: [] }],
      filterValue: {
        hasEmptyValue: '',
        hasValueEqual: '86400',
        hasValueLower: '86400',
        hasValueLowerOrEqual: '86400',
        hasValueHigher: '86400',
        hasValueHigherOrEqual: '86400',
      },

      expected: {
        hasEmptyValue: true,
        hasValueEqual: false,
        hasValueLower: false,
        hasValueLowerOrEqual: false,
        hasValueHigher: false,
        hasValueHigherOrEqual: false,
      },
    },

    {
      rowValue: [{ id: 1, value: 100 }],
      filterValue: {
        hasEmptyValue: '',
        hasValueEqual: '200',
        hasValueLower: '200',
        hasValueLowerOrEqual: '200',
        hasValueHigher: '200',
        hasValueHigherOrEqual: '200',
      },

      expected: {
        hasEmptyValue: false,
        hasValueEqual: false,
        hasValueLower: true,
        hasValueLowerOrEqual: true,
        hasValueHigher: false,
        hasValueHigherOrEqual: false,
      },
    },

    {
      rowValue: [
        { id: 1, value: 100 },
        { id: 2, value: 200 },
      ],
      filterValue: {
        hasEmptyValue: '',
        hasValueEqual: '200',
        hasValueLower: '200',
        hasValueLowerOrEqual: '200',
        hasValueHigher: '200',
        hasValueHigherOrEqual: '200',
      },

      expected: {
        hasEmptyValue: false,
        hasValueEqual: true,
        hasValueLower: true,
        hasValueLowerOrEqual: true,
        hasValueHigher: false,
        hasValueHigherOrEqual: true,
      },
    },

    {
      rowValue: [
        { id: 1, value: 100 },
        { id: 2, value: 200 },
      ],
      filterValue: {
        hasEmptyValue: '',
        hasValueEqual: '101',
        hasValueLower: '101',
        hasValueLowerOrEqual: '101',
        hasValueHigher: '101',
        hasValueHigherOrEqual: '101',
      },

      expected: {
        hasEmptyValue: false,
        hasValueEqual: false,
        hasValueLower: true,
        hasValueLowerOrEqual: false,
        hasValueHigher: true,
        hasValueHigherOrEqual: true,
      },
    },
  ]

  test.each(DurationLookupFilterCases)(
    'duration lookup has empty value %j.',
    (values) => {
      const result = new HasEmptyValueViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasEmptyValue,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasEmptyValue)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has not empty value %j.',
    (values) => {
      const result = new HasNotEmptyValueViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasEmptyValue,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasEmptyValue)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has value equal %j.',
    (values) => {
      const result = new HasValueEqualViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueEqual,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasValueEqual)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has not value equal %j.',
    (values) => {
      const result = new HasNotValueEqualViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueEqual,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasValueEqual)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has value lower %j.',
    (values) => {
      const result = new HasValueLowerThanViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueLower,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasValueLower)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has not value lower %j.',
    (values) => {
      const result = new HasNotValueLowerThanViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueLower,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasValueLower)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has value higher %j.',
    (values) => {
      const result = new HasValueHigherThanViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueHigher,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasValueHigher)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has not value higher %j.',
    (values) => {
      const result = new HasNotValueHigherThanViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueHigher,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasValueHigher)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has value higher or equal %j.',
    (values) => {
      const result = new HasValueHigherThanOrEqualViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueHigherOrEqual,
        field,
        fieldType
      )
      expect(result).toBe(values.expected.hasValueHigherOrEqual)
    }
  )

  test.each(DurationLookupFilterCases)(
    'duration lookup has not value higher or equal %j.',
    (values) => {
      const result = new HasNotValueHigherThanOrEqualViewFilterType({
        app: testApp.getApp(),
      }).matches(
        values.rowValue,
        values.filterValue.hasValueHigherOrEqual,
        field,
        fieldType
      )
      expect(result).toBe(!values.expected.hasValueHigherOrEqual)
    }
  )
})
