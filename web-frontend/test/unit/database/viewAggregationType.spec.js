import { TestApp } from '@baserow/test/helpers/testApp'
import {
  DateFieldType,
  DurationFieldType,
  NumberFieldType,
  RatingFieldType,
} from '@baserow/modules/database/fieldTypes'

const testData = {
  empty_count: {
    inputValue: 25,
    expectedResult: 25,
    context: {},
  },
  not_empty_count: {
    inputValue: 25,
    expectedResult: 75,
    context: { rowCount: 100 },
  },
  empty_percentage: {
    inputValue: 25,
    expectedResult: '25%',
    context: { rowCount: 100 },
  },
  not_empty_percentage: {
    inputValue: 25,
    expectedResult: '75%',
    context: { rowCount: 100 },
  },
  checked_count: {
    inputValue: 25,
    expectedResult: 75,
    context: { rowCount: 100 },
  },
  not_checked_count: {
    inputValue: 25,
    expectedResult: 25,
    context: { rowCount: 100 },
  },
  checked_percentage: {
    inputValue: 25,
    expectedResult: '75%',
    context: { rowCount: 100 },
  },
  not_checked_percentage: {
    inputValue: 25,
    expectedResult: '25%',
    context: { rowCount: 100 },
  },
  min: [
    {
      inputValue: 25,
      expectedResult: '25',
      context: {
        rowCount: 100,
        field: { type: 'number' },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: 60,
      expectedResult: '0:01:00',
      context: {
        rowCount: 100,
        field: { type: 'duration', duration_format: 'h:mm:ss' },
        fieldType: new DurationFieldType(),
      },
    },
  ],
  max: [
    {
      inputValue: 25,
      expectedResult: '25',
      context: {
        rowCount: 100,
        field: { type: 'number' },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: 60,
      expectedResult: '0:01:00',
      context: {
        rowCount: 100,
        field: { type: 'duration', duration_format: 'h:mm:ss' },
        fieldType: new DurationFieldType(),
      },
    },
  ],
  max_date: {
    inputValue: new Date(2018, 11, 24, 10, 33, 30, 0).toISOString(),
    expectedResult: '24/12/2018',
    context: {
      rowCount: 100,
      field: {
        timezone: 'Europe/London',
        date_format: 'EU',
        date_include_time: false,
      },
      fieldType: new DateFieldType(),
    },
  },
  min_date: {
    inputValue: new Date(2018, 11, 24, 10, 33, 30, 0).toISOString(),
    expectedResult: '24/12/2018',
    context: {
      rowCount: 100,
      field: {
        timezone: 'Europe/London',
        date_format: 'EU',
        date_include_time: false,
      },
      fieldType: new DateFieldType(),
    },
  },
  sum: [
    {
      inputValue: 25,
      expectedResult: '25.00',
      context: {
        rowCount: 100,
        field: { type: 'number', number_decimal_places: 2 },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: 60,
      expectedResult: '0:01',
      context: {
        rowCount: 100,
        field: { type: 'duration', duration_format: 'h:mm' },
        fieldType: new DurationFieldType(),
      },
    },
  ],
  average: [
    {
      inputValue: 25.2193712987,
      expectedResult: '25.219',
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: 25.2193712987,
      expectedResult: 25.2193712987,
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
  std_dev: [
    {
      inputValue: 25.2193712987,
      expectedResult: '25.219',
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: 25.2193712987,
      expectedResult: 25.2193712987,
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
  variance: [
    {
      inputValue: 25.2193712987,
      expectedResult: '25.219',
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: 25.2193712987,
      expectedResult: 25.2193712987,
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
  unique: [
    {
      inputValue: 25.2193712987,
      expectedResult: '25.219',
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: 25.2193712987,
      expectedResult: 25.2193712987,
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
}

const testDataError = {
  empty_count: {
    inputValue: 'test',
    expectedResult: null,
    context: {},
  },
  checked_count: {
    inputValue: undefined,
    expectedResult: null,
    context: { rowCount: 100 },
  },
  min: {
    inputValue: null,
    expectedResult: null,
    context: { rowCount: 100 },
  },
  max: {
    inputValue: null,
    expectedResult: null,
    context: { rowCount: 100 },
  },
  max_date: {
    inputValue: 0,
    expectedResult: null,
    context: {
      rowCount: 100,
      field: {
        timezone: 'Europe/London',
        date_format: 'EU',
        date_include_time: false,
      },
      fieldType: new DateFieldType(),
    },
  },
  min_date: {
    inputValue: 0,
    expectedResult: null,
    context: {
      rowCount: 100,
      field: {
        timezone: 'Europe/London',
        date_format: 'EU',
        date_include_time: false,
      },
      fieldType: new DateFieldType(),
    },
  },
  sum: {
    inputValue: null,
    expectedResult: null,
    context: { rowCount: 100 },
  },
  average: [
    {
      inputValue: null,
      expectedResult: '',
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: null,
      expectedResult: '',
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
  std_dev: [
    {
      inputValue: null,
      expectedResult: '',
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: null,
      expectedResult: '',
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
  variance: [
    {
      inputValue: null,
      expectedResult: '',
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: null,
      expectedResult: '',
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
  unique: [
    {
      inputValue: null,
      expectedResult: null,
      context: {
        rowCount: 100,
        field: {
          type: 'number',
          number_type: 'DECIMAL',
          number_decimal_places: 3,
        },
        fieldType: new NumberFieldType(),
      },
    },
    {
      inputValue: null,
      expectedResult: null,
      context: {
        rowCount: 100,
        field: {
          type: 'rating',
        },
        fieldType: new RatingFieldType(),
      },
    },
  ],
}

describe('View Aggregation Tests', () => {
  let testApp = null
  let store = null

  beforeAll(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('Test field value', () => {
    store.$registry
      .getOrderedList('viewAggregation')
      .forEach((aggregationType) => {
        // Get test data for this aggregation type
        let dataset = testData[aggregationType.getType()]
        if (dataset) {
          if (!Array.isArray(dataset)) {
            dataset = [dataset]
          }
          dataset.forEach(({ inputValue, expectedResult, context }) => {
            const actualResult = aggregationType.getValue(inputValue, context)
            expect(actualResult).toEqual(expectedResult)
          })
        }
      })
  })

  test('Test field empty value', () => {
    store.$registry
      .getOrderedList('viewAggregation')
      .forEach((aggregationType) => {
        // Get test data for this aggregation type
        let dataset = testDataError[aggregationType.getType()]
        if (dataset) {
          if (!Array.isArray(dataset)) {
            dataset = [dataset]
          }
          dataset.forEach(({ inputValue, expectedResult, context }) => {
            const actualResult = aggregationType.getValue(inputValue, context)
            expect(actualResult).toEqual(expectedResult)
          })
        }
      })
  })
})
