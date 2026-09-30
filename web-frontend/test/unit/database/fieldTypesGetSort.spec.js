import path from 'path'
import fs from 'fs'

import {
  TextFieldType,
  SingleSelectFieldType,
  MultipleSelectFieldType,
  MultipleCollaboratorsFieldType,
} from '@baserow/modules/database/fieldTypes'
import { firstBy } from 'thenby'
import { TestApp } from '@baserow/test/helpers/testApp'
import {
  getGroupByRowSortFunction,
  getRowSortFunction,
} from '@baserow/modules/database/utils/view'

const testTableData = [
  {
    id: 1,
    order: '1.00000000000000000000',
    field_272: 'Tesla',
    field_275: [{ id: 146, value: 'C', color: 'red' }],
  },
  {
    id: 2,
    order: '2.00000000000000000000',
    field_272: 'Amazon',
    field_275: [{ id: 144, value: 'A', color: 'blue' }],
  },
  {
    id: 3,
    order: '3.00000000000000000000',
    field_272: '',
    field_275: [
      { id: 144, value: 'A', color: 'blue' },
      { id: 145, value: 'B', color: 'orange' },
    ],
  },
  {
    id: 4,
    order: '4.00000000000000000000',
    field_272: '',
    field_275: [
      { id: 144, value: 'A', color: 'blue' },
      { id: 145, value: 'B', color: 'orange' },
      { id: 146, value: 'C', color: 'red' },
    ],
  },
  {
    id: 5,
    order: '5.00000000000000000000',
    field_272: '',
    field_275: [
      { id: 149, value: 'F', color: 'light-gray' },
      { id: 148, value: 'E', color: 'dark-red' },
    ],
  },
  {
    id: 6,
    order: '6.00000000000000000000',
    field_272: '',
    field_275: [
      { id: 149, value: 'F', color: 'light-gray' },
      { id: 144, value: 'A', color: 'blue' },
    ],
  },
]

const testTableDataWithNull = [
  {
    id: 1,
    order: '1.00000000000000000000',
    field_272: 'Tesla',
    field_275: [],
  },
  {
    id: 2,
    order: '2.00000000000000000000',
    field_272: 'Amazon',
    field_275: [{ id: 144, value: 'A', color: 'blue' }],
  },
  {
    id: 3,
    order: '3.00000000000000000000',
    field_272: '',
    field_275: [
      { id: 144, value: 'A', color: 'blue' },
      { id: 145, value: 'B', color: 'orange' },
    ],
  },
]

describe('MultipleSelectFieldType sorting', () => {
  let testApp = null
  let multipleSelectFieldType = null
  let ASC = null
  let DESC = null
  let sortASC = firstBy()
  let sortDESC = firstBy()

  beforeEach(() => {
    testApp = new TestApp()
    multipleSelectFieldType = new MultipleSelectFieldType()
    ASC = multipleSelectFieldType.getSort('field_275', 'ASC')
    DESC = multipleSelectFieldType.getSort('field_275', 'DESC')
    sortASC = sortASC.thenBy(ASC)
    sortDESC = sortDESC.thenBy(DESC)
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('ascending and descending order', () => {
    testTableData.sort(sortASC)
    let ids = testTableData.map((obj) => obj.id)
    expect(ids).toEqual([2, 3, 4, 1, 6, 5])

    testTableData.sort(sortDESC)
    ids = testTableData.map((obj) => obj.id)
    expect(ids).toEqual([5, 6, 1, 4, 3, 2])
  })

  test('ascending and descending order with null values', () => {
    testTableDataWithNull.sort(sortASC)
    let ids = testTableDataWithNull.map((obj) => obj.id)
    expect(ids).toEqual([1, 2, 3])

    testTableDataWithNull.sort(sortDESC)
    ids = testTableDataWithNull.map((obj) => obj.id)
    expect(ids).toEqual([3, 2, 1])
  })

  test('sort matches backend', () => {
    // This is a naive sorting test running on Node.js and thus not really testing
    // collation sorting in the browsers where this functionality is mostly used The
    // Peseta character in particular seems to be sorted differently in our Node.js,
    // hence it will be ignored for this test
    const sortedChars = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/sorted_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const data = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/all_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const rows = Array.from(data).map((value) => {
      return { v: [{ value }] }
    })
    const sortFunction = new MultipleSelectFieldType().getSort('v', 'ASC')
    rows.sort(sortFunction)
    const result = rows.map((v) => v.v[0].value).join('')
    expect(result).toBe(sortedChars)
  })
})

describe('TextFieldType sorting', () => {
  test('sort matches backend', () => {
    // This is a naive sorting test running on Node.js
    // and thus not really testing collation sorting in
    // the browsers where this functionality is mostly used
    // The Peseta character in particular seems to be
    // sorted differently in our Node.js, hence it will be
    // ignored for this test
    const sortedChars = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/sorted_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const data = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/all_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const chars = Array.from(data).map((value) => {
      return { v: value }
    })
    const sortFunction = new TextFieldType().getSort('v', 'ASC')
    chars.sort(sortFunction)
    const result = chars.map((value) => value.v).join('')
    expect(result).toBe(sortedChars)
  })
})

describe('SingleSelectFieldType sorting', () => {
  test('sort matches backend', () => {
    // This is a naive sorting test running on Node.js and thus not really testing
    // collation sorting in the browsers where this functionality is mostly used The
    // Peseta character in particular seems to be sorted differently in our Node.js,
    // hence it will be ignored for this test
    const sortedChars = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/sorted_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const data = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/all_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const rows = Array.from(data).map((value) => {
      return { v: { value } }
    })
    const sortFunction = new SingleSelectFieldType().getSort('v', 'ASC')
    rows.sort(sortFunction)
    const result = rows.map((v) => v.v.value).join('')
    expect(result).toBe(sortedChars)
  })
})

describe('MultipleCollaboratorsFieldType sorting', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('sort matches backend', () => {
    // This is a naive sorting test running on Node.js and thus not really testing
    // collation sorting in the browsers where this functionality is mostly used The
    // Peseta character in particular seems to be sorted differently in our Node.js,
    // hence it will be ignored for this test
    const sortedChars = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/sorted_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const data = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/all_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const rows = Array.from(data).map((value) => {
      return { v: [{ name: value }] }
    })
    const sortFunction = new MultipleCollaboratorsFieldType({
      app: testApp,
    }).getSort('v', 'ASC')
    rows.sort(sortFunction)
    const result = rows.map((v) => v.v[0].name).join('')
    expect(result).toBe(sortedChars)
  })
})

describe('LinkRowFieldType sorting text values according to collation', () => {
  let testApp = null
  let linkRowFieldType = null

  beforeEach(() => {
    testApp = new TestApp()
    linkRowFieldType = testApp._app.$registry.registry.field.link_row
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('sort matches backend', () => {
    // This is a naive sorting test running on Node.js and thus not really testing
    // collation sorting in the browsers where this functionality is mostly used The
    // Peseta character in particular seems to be sorted differently in our Node.js,
    // hence it will be ignored for this test
    const sortedChars = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/sorted_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const data = fs
      .readFileSync(
        path.join(__dirname, '/../../../../tests/all_chars.txt'),
        'utf8'
      )
      .replace(/^\uFEFF/, '') // strip BOM
      .replace('₧', '') // ignore Peseta
    const rows = Array.from(data).map((value) => {
      return { v: [{ value }] }
    })
    const relatedField = { type: 'text' }
    const linkRowField = {
      link_row_table_primary_field: relatedField,
    }
    const sortFunction = linkRowFieldType.getSort('v', 'ASC', linkRowField)
    rows.sort(sortFunction)
    const result = rows.map((v) => v.v[0].value).join('')
    expect(result).toBe(sortedChars)
  })
})

describe('LinkRowFieldType sorting with other primary fields', () => {
  let testApp = null
  let linkRowFieldType = null

  beforeEach(() => {
    testApp = new TestApp()
    linkRowFieldType = testApp._app.$registry.registry.field.link_row
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('ascending and descending order with number primary field', () => {
    const testData = [
      {
        id: 1,
        order: '1.00000000000000000000',
        field_link: [
          { id: 1, value: '100' },
          { id: 2, value: '50' },
        ],
      },
      {
        id: 2,
        order: '2.00000000000000000000',
        field_link: [{ id: 3, value: '25' }],
      },
      {
        id: 3,
        order: '3.00000000000000000000',
        field_link: [{ id: 4, value: '' }],
      },
      {
        id: 4,
        order: '4.00000000000000000000',
        field_link: [],
      },
      {
        id: 5,
        order: '5.00000000000000000000',
        field_link: [{ id: 5, value: '75' }],
      },
      {
        id: 6,
        order: '6.00000000000000000000',
        field_link: [{ id: 6, value: '25' }],
      },
      {
        id: 7,
        order: '7.00000000000000000000',
        field_link: [
          { id: 1, value: '100' },
          { id: 6, value: '25' },
        ],
      },
    ]

    const relatedField = {
      type: 'number',
      number_decimal_places: 0,
    }
    const linkRowField = {
      link_row_table_primary_field: relatedField,
    }
    const sortASC = linkRowFieldType.getSort('field_link', 'ASC', linkRowField)
    const sortDESC = linkRowFieldType.getSort(
      'field_link',
      'DESC',
      linkRowField
    )

    testData.sort(sortASC)
    let ids = testData.map((obj) => obj.id)
    expect(ids).toEqual([4, 2, 6, 5, 7, 1, 3])

    testData.sort(sortDESC)
    ids = testData.map((obj) => obj.id)
    expect(ids).toEqual([4, 3, 1, 7, 5, 2, 6])
  })

  test('ascending and descending order with duration primary field', () => {
    const testData = [
      {
        id: 1,
        order: '1.00000000000000000000',
        field_link: [
          { id: 1, value: '0:01:40' },
          { id: 2, value: '0:00:50' },
        ],
      },
      {
        id: 2,
        order: '2.00000000000000000000',
        field_link: [{ id: 3, value: '0:00:25' }],
      },
      {
        id: 3,
        order: '3.00000000000000000000',
        field_link: [{ id: 4, value: '' }],
      },
      {
        id: 4,
        order: '4.00000000000000000000',
        field_link: [],
      },
      {
        id: 5,
        order: '5.00000000000000000000',
        field_link: [{ id: 5, value: '0:01:15' }],
      },
      {
        id: 6,
        order: '6.00000000000000000000',
        field_link: [{ id: 6, value: '0:00:25' }],
      },
      {
        id: 7,
        order: '7.00000000000000000000',
        field_link: [
          { id: 1, value: '0:01:40' },
          { id: 6, value: '0:00:25' },
        ],
      },
    ]

    const relatedField = {
      type: 'duration',
      duration_format: 'h:mm:ss',
    }
    const linkRowField = {
      link_row_table_primary_field: relatedField,
    }
    const sortASC = linkRowFieldType.getSort('field_link', 'ASC', linkRowField)
    const sortDESC = linkRowFieldType.getSort(
      'field_link',
      'DESC',
      linkRowField
    )

    testData.sort(sortASC)
    let ids = testData.map((obj) => obj.id)
    // Nulls first, then sorted by the lowest number value in the linked rows
    expect(ids).toEqual([4, 2, 6, 5, 7, 1, 3])

    testData.sort(sortDESC)
    ids = testData.map((obj) => obj.id)
    // Nulls first, then sorted by the highest number value in the linked rows
    expect(ids).toEqual([4, 3, 1, 7, 5, 2, 6])
  })

  test('ascending and descending order with date primary field', () => {
    const testData = [
      {
        id: 1,
        order: '1.00000000000000000000',
        field_link: [
          { id: 1, value: '06/12/2024 11:30' },
          { id: 2, value: '06/12/2024 01:00' },
        ],
      },
      {
        id: 2,
        order: '2.00000000000000000000',
        field_link: [{ id: 3, value: '05/12/2024 07:00' }],
      },
      {
        id: 3,
        order: '3.00000000000000000000',
        field_link: [{ id: 4, value: '' }],
      },
      {
        id: 4,
        order: '4.00000000000000000000',
        field_link: [],
      },
      {
        id: 5,
        order: '5.00000000000000000000',
        field_link: [{ id: 5, value: '06/12/2024 09:00' }],
      },
      {
        id: 6,
        order: '6.00000000000000000000',
        field_link: [{ id: 6, value: '05/12/2024 07:00' }],
      },
      {
        id: 7,
        order: '7.00000000000000000000',
        field_link: [
          { id: 1, value: '06/12/2024 11:30' },
          { id: 6, value: '05/12/2024 07:00' },
        ],
      },
    ]

    const relatedField = {
      type: 'date',
      date_format: 'EU',
      date_time_format: '24',
      date_include_time: true,
      date_force_timezone: 'UTC',
    }
    const linkRowField = {
      link_row_table_primary_field: relatedField,
    }
    const sortASC = linkRowFieldType.getSort('field_link', 'ASC', linkRowField)
    const sortDESC = linkRowFieldType.getSort(
      'field_link',
      'DESC',
      linkRowField
    )

    testData.sort(sortASC)
    let ids = testData.map((obj) => obj.id)
    // Nulls first, then sorted by the lowest number value in the linked rows
    expect(ids).toEqual([4, 2, 6, 5, 7, 1, 3])

    testData.sort(sortDESC)
    ids = testData.map((obj) => obj.id)
    // Nulls first, then sorted by the highest number value in the linked rows
    expect(ids).toEqual([4, 3, 1, 7, 5, 2, 6])
  })
})

// A row inserted by a realtime event may not carry every field yet, so the
// sort functions must accept a missing or null cell.
describe('sorting rows with a missing cell value', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('SingleSelectFieldType sorts a missing value first', () => {
    const rows = [
      { id: 1, f: { id: 2, value: 'B' } },
      { id: 2 },
      { id: 3, f: null },
      { id: 4, f: { id: 1, value: 'A' } },
    ]

    rows.sort(new SingleSelectFieldType().getSort('f', 'ASC'))

    expect(rows.map((row) => row.id)).toEqual([2, 3, 4, 1])
  })

  test.each([
    ['text', 'b', 'a'],
    ['date', '2026-02-01', '2026-01-01'],
  ])(
    'an array formula of %s sorts a null or missing value first',
    (arrayFormulaType, later, earlier) => {
      const registry = testApp.store.$registry
      const field = {
        formula_type: 'array',
        array_formula_type: arrayFormulaType,
        date_format: 'ISO',
        date_include_time: false,
      }
      const rows = [
        { id: 1, f: [{ id: 1, value: later }] },
        { id: 2, f: null },
        { id: 3 },
        { id: 4, f: [{ id: 2, value: earlier }] },
      ]

      rows.sort(
        registry.get('formula_type', 'array').getSort('f', 'ASC', field)
      )

      expect(rows.map((row) => row.id)).toEqual([2, 3, 4, 1])
    }
  )

  test('an array formula of numbers sorts zero after an empty cell', () => {
    const registry = testApp.store.$registry
    const field = {
      formula_type: 'array',
      array_formula_type: 'number',
      number_decimal_places: 0,
    }
    const rows = [
      { id: 1, f: [{ id: 1, value: 5 }] },
      { id: 2, f: [{ id: 2, value: 0 }] },
      { id: 3 },
    ]

    rows.sort(registry.get('formula_type', 'array').getSort('f', 'ASC', field))

    expect(rows.map((row) => row.id)).toEqual([3, 2, 1])
  })

  const primaryField = { id: 9, type: 'text', primary: true }
  const cases = [
    ['text', 'text', {}, 'b', 'a'],
    ['number', 'number', { number_decimal_places: 0 }, '2', '1'],
    ['rating', 'rating', {}, 2, 1],
    [
      'multiple_select',
      'multiple_select',
      {},
      [{ id: 2, value: 'B' }],
      [{ id: 1, value: 'A' }],
    ],
    [
      'link_row',
      'link_row',
      { link_row_table_primary_field: primaryField },
      [{ id: 2, value: 'b' }],
      [{ id: 1, value: 'a' }],
    ],
    [
      'multiple_collaborators',
      'multiple_collaborators',
      {},
      [{ id: 2, name: 'b' }],
      [{ id: 1, name: 'a' }],
    ],
    [
      'created_by',
      'created_by',
      {},
      { id: 2, name: 'b' },
      { id: 1, name: 'a' },
    ],
    [
      'last_modified_by',
      'last_modified_by',
      {},
      { id: 2, name: 'b' },
      { id: 1, name: 'a' },
    ],
  ]
  // A failed save can also write the old value back as a present but undefined
  // key.
  describe.each([
    ['missing', {}],
    ['undefined', { field_1: undefined }],
    // A converted field can leave null in the buffer until the rows refetch.
    ['null', { field_1: null }],
  ])('with a %s cell', (_, missingCell) => {
    test.each(cases)(
      'getRowSortFunction sorts a %s cell like an empty one',
      (_label, type, fieldProps, later, earlier) => {
        const registry = testApp.store.$registry
        const field = { id: 1, type, ...fieldProps }
        const rows = [
          { id: 1, order: '1', field_1: later },
          { id: 2, order: '2', ...missingCell },
          { id: 3, order: '3', field_1: earlier },
          {
            id: 4,
            order: '4',
            field_1: registry.get('field', type).getEmptyValue(field),
          },
        ]

        rows.sort(
          getRowSortFunction(
            registry,
            [{ field: 1, order: 'ASC', type: 'default' }],
            [field]
          )
        )

        expect(rows.map((row) => row.id)).toEqual([2, 4, 3, 1])
      }
    )
  })

  test.each([
    ['missing', {}],
    ['null', { field_1: null }],
  ])(
    'getGroupByRowSortFunction sorts a %s link row cell like an empty one',
    (_, emptyCell) => {
      const registry = testApp.store.$registry
      const field = {
        id: 1,
        type: 'link_row',
        link_row_table_primary_field: { id: 9, type: 'text', primary: true },
      }
      const rows = [
        { id: 1, field_1: [{ id: 2, value: 'b' }] },
        { id: 2, ...emptyCell },
        { id: 3, field_1: [{ id: 1, value: 'a' }] },
      ]

      rows.sort(
        getGroupByRowSortFunction(
          registry,
          [field],
          [{ field: 1, order: 'ASC', type: 'default' }]
        )
      )

      expect(rows.map((row) => row.id)).toEqual([2, 3, 1])
    }
  )
})
