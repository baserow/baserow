import {
  prepareRowForRequest,
  prepareNewOldAndUpdateRequestValues,
  extractRowReadOnlyValues,
  computeMultiSelectPosition,
  computeRowMatchFlags,
  buildNewRowDefaults,
  computeRowInsertPosition,
} from '@baserow/modules/database/utils/row'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Row utilities', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  describe('prepareRowForRequest', () => {
    const rowsToTest = [
      // Empty case
      {
        input: {
          row: {},
          fields: [],
        },
        output: {},
      },
      // Basic case of just a simple text field
      {
        input: {
          row: {
            field_1: 'value',
          },
          fields: [
            {
              name: 'field_1',
              id: 1,
              type: 'text',
            },
          ],
        },
        output: {
          field_1: 'value',
        },
      },
      // Empty value is being used if no value is provided
      {
        input: {
          row: {
            field_1: 'value',
          },
          fields: [
            {
              name: 'field_1',
              id: 1,
              type: 'text',
            },
            {
              name: 'field_2',
              id: 2,
              text_default: 'some default',
              type: 'text',
            },
          ],
        },
        output: {
          field_1: 'value',
          field_2: 'some default',
        },
      },
      // Read only field
      {
        input: {
          row: {
            field_1: 'value',
          },
          fields: [
            {
              name: 'field_1',
              id: 1,
              type: 'formula',
            },
          ],
        },
        output: {},
      },
      // Missing value
      {
        input: {
          row: {},
          fields: [
            {
              name: 'field_1',
              id: 1,
              text_default: 'some default',
              type: 'text',
            },
          ],
        },
        output: {
          field_1: 'some default',
        },
      },
    ]

    test.each(rowsToTest)(
      'that %o is correctly prepared for request',
      ({ input, output }) => {
        expect(
          prepareRowForRequest(input.row, input.fields, store.$registry)
        ).toEqual(output)
      },
      200
    )
  })

  test('prepareNewOldAndUpdateRequestValues', () => {
    const row = {
      id: 1,
      field_1: { id: 2, value: 'Option 2', color: 'green' },
      field_2: '2024-01-04T15:15:59.163126Z',
      field_3: 'Text',
    }
    const allFields = [
      {
        id: 1,
        name: 'Single Select',
        type: 'single_select',
        select_options: [
          {
            id: 1,
            value: 'Option 1',
            color: 'blue',
          },
          {
            id: 2,
            value: 'Option 2',
            color: 'green',
          },
        ],
      },
      {
        id: 2,
        name: 'Last modified',
        type: 'last_modified',
        date_include_time: true,
      },
      {
        id: 3,
        name: 'Text',
        type: 'text',
      },
    ]
    const field = allFields[0]
    const value = { id: 1, value: 'Option 1', color: 'blue' }
    const oldValue = { id: 2, value: 'Option 2', color: 'green' }

    const { newRowValues, oldRowValues, updateRequestValues } =
      prepareNewOldAndUpdateRequestValues(
        row,
        allFields,
        field,
        value,
        oldValue,
        store.$registry
      )

    expect(newRowValues.field_2).not.toBe(oldRowValues.field_2)
    expect(newRowValues).toEqual({
      id: row.id,
      field_1: { id: 1, value: 'Option 1', color: 'blue' },
      field_2: newRowValues.field_2,
    })
    expect(oldRowValues).toEqual({
      id: row.id,
      field_1: { id: 2, value: 'Option 2', color: 'green' },
      field_2: '2024-01-04T15:15:59.163126Z',
    })
    expect(updateRequestValues).toEqual({
      field_1: 1,
      id: row.id,
    })
  })

  describe('computeMultiSelectPosition', () => {
    const area = (extra) => ({
      isAreaSelectionActive: true,
      isCheckboxSelected: false,
      rowIndexRange: [0, 2],
      fieldIndexRange: [0, 2],
      ...extra,
    })

    test('no area selection and no checkbox returns all false', () => {
      expect(
        computeMultiSelectPosition({
          isAreaSelectionActive: false,
          isCheckboxSelected: false,
          rowIndex: 1,
          fieldIndex: 1,
        })
      ).toEqual({
        selected: false,
        top: false,
        right: false,
        bottom: false,
        left: false,
      })
    })

    test('no area selection with selected checkbox returns selected only', () => {
      const pos = computeMultiSelectPosition({
        isAreaSelectionActive: false,
        isCheckboxSelected: true,
        rowIndex: 1,
        fieldIndex: 1,
      })
      expect(pos.selected).toBe(true)
      expect(pos.top).toBe(false)
      expect(pos.left).toBe(false)
    })

    test('area selection with cell inside rectangle returns selected only', () => {
      expect(
        computeMultiSelectPosition(area({ rowIndex: 1, fieldIndex: 1 }))
      ).toEqual({
        selected: true,
        top: false,
        right: false,
        bottom: false,
        left: false,
      })
    })

    test('area selection with top-left corner returns top and left borders', () => {
      expect(
        computeMultiSelectPosition(area({ rowIndex: 0, fieldIndex: 0 }))
      ).toEqual({
        selected: true,
        top: true,
        right: false,
        bottom: false,
        left: true,
      })
    })

    test('area selection with bottom-right corner returns bottom and right borders', () => {
      expect(
        computeMultiSelectPosition(area({ rowIndex: 2, fieldIndex: 2 }))
      ).toEqual({
        selected: true,
        top: false,
        right: true,
        bottom: true,
        left: false,
      })
    })

    test('area selection with one cell rectangle returns all four borders', () => {
      expect(
        computeMultiSelectPosition(
          area({
            rowIndex: 1,
            fieldIndex: 1,
            rowIndexRange: [1, 1],
            fieldIndexRange: [1, 1],
          })
        )
      ).toEqual({
        selected: true,
        top: true,
        right: true,
        bottom: true,
        left: true,
      })
    })

    test('area selection with row outside range returns not selected', () => {
      expect(
        computeMultiSelectPosition(area({ rowIndex: 5, fieldIndex: 1 }))
          .selected
      ).toBe(false)
    })

    test('area selection with field outside range returns not selected', () => {
      expect(
        computeMultiSelectPosition(area({ rowIndex: 1, fieldIndex: 5 }))
          .selected
      ).toBe(false)
    })

    test('area selection with negative row index returns not selected', () => {
      expect(
        computeMultiSelectPosition(area({ rowIndex: -1, fieldIndex: 1 }))
          .selected
      ).toBe(false)
    })
  })

  describe('computeRowMatchFlags', () => {
    const textField = { id: 1, name: 'Name', type: 'text', primary: true }
    const baseView = (extra = {}) => ({
      filters_disabled: true,
      filter_type: 'AND',
      filter_groups: [],
      filters: [],
      sortings: [],
      ...extra,
    })

    test('filters disabled makes matchFilters true regardless of row values', () => {
      const { matchFilters } = computeRowMatchFlags({
        row: { id: 1, field_1: 'anything' },
        view: baseView({ filters_disabled: true }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [{ id: 1, field_1: 'anything' }],
      })
      expect(matchFilters).toBe(true)
    })

    test('enabled equal filter returns matchFilters true for matching row', () => {
      const { matchFilters } = computeRowMatchFlags({
        row: { id: 1, field_1: 'Alice' },
        view: baseView({
          filters_disabled: false,
          filters: [
            { id: 1, view: 1, field: 1, type: 'equal', value: 'Alice' },
          ],
        }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [{ id: 1, field_1: 'Alice' }],
      })
      expect(matchFilters).toBe(true)
    })

    test('enabled equal filter returns matchFilters false for non-matching row', () => {
      const { matchFilters } = computeRowMatchFlags({
        row: { id: 1, field_1: 'Bob' },
        view: baseView({
          filters_disabled: false,
          filters: [
            { id: 1, view: 1, field: 1, type: 'equal', value: 'Alice' },
          ],
        }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [{ id: 1, field_1: 'Bob' }],
      })
      expect(matchFilters).toBe(false)
    })

    test('row that is the only member of its sort group matches sorting', () => {
      const { matchSortings } = computeRowMatchFlags({
        row: { id: 1, field_1: 'Z' },
        view: baseView({
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [{ id: 1, field_1: 'Z' }],
      })
      expect(matchSortings).toBe(true)
    })

    test('row at its sorted position matches sorting', () => {
      const { matchSortings } = computeRowMatchFlags({
        row: { id: 1, field_1: 'A' },
        view: baseView({
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [
          { id: 1, field_1: 'A' },
          { id: 2, field_1: 'B' },
        ],
      })
      expect(matchSortings).toBe(true)
    })

    test('row out of sorted position does not match sorting', () => {
      const { matchSortings } = computeRowMatchFlags({
        row: { id: 99, field_1: 'A' },
        view: baseView({
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [
          { id: 2, field_1: 'Z' },
          { id: 99, field_1: 'A' },
        ],
      })
      expect(matchSortings).toBe(false)
    })

    test('sorting uses the updated row values even if the comparison set is stale', () => {
      const { matchSortings } = computeRowMatchFlags({
        row: { id: 99, field_1: 'A' },
        view: baseView({
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [
          { id: 1, field_1: 'B' },
          { id: 99, field_1: 'Z' },
        ],
      })
      expect(matchSortings).toBe(false)
    })

    test('row absent from rowsInSortingGroup matches sorting by default', () => {
      const { matchSortings } = computeRowMatchFlags({
        row: { id: 99, field_1: 'A' },
        view: baseView({
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        }),
        fields: [textField],
        registry: store.$registry,
        rowsInSortingGroup: [{ id: 1, field_1: 'B' }],
      })
      expect(matchSortings).toBe(true)
    })

    test('lookup (array formula) field sort correctly compares array values', () => {
      const lookupField = {
        id: 2,
        name: 'Lookup',
        type: 'formula',
        formula_type: 'array',
        array_formula_type: 'text',
      }
      const rows = [
        {
          id: 1,
          order: '1.00000000000000000000',
          field_2: [{ id: 20, value: 'Alpha' }],
        },
        {
          id: 2,
          order: '2.00000000000000000000',
          field_2: [{ id: 20, value: 'Alpha' }],
        },
        {
          id: 3,
          order: '3.00000000000000000000',
          field_2: [{ id: 10, value: 'Beta' }],
        },
      ]
      const { matchSortings } = computeRowMatchFlags({
        row: { id: 2, field_2: [{ id: 20, value: 'Alpha' }] },
        view: baseView({
          sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        }),
        fields: [lookupField],
        registry: store.$registry,
        rowsInSortingGroup: rows,
      })
      expect(matchSortings).toBe(true)
    })

    test('lookup field sort detects row out of position', () => {
      const lookupField = {
        id: 2,
        name: 'Lookup',
        type: 'formula',
        formula_type: 'array',
        array_formula_type: 'text',
      }
      const rows = [
        {
          id: 1,
          order: '1.00000000000000000000',
          field_2: [{ id: 10, value: 'Beta' }],
        },
        {
          id: 2,
          order: '2.00000000000000000000',
          field_2: [{ id: 20, value: 'Alpha' }],
        },
      ]
      const { matchSortings } = computeRowMatchFlags({
        row: { id: 2, field_2: [{ id: 20, value: 'Alpha' }] },
        view: baseView({
          sortings: [{ field: 2, order: 'ASC', type: 'default' }],
        }),
        fields: [lookupField],
        registry: store.$registry,
        rowsInSortingGroup: rows,
      })
      expect(matchSortings).toBe(false)
    })

    test('computeRowInsertPosition sorts lookup array values correctly', () => {
      const lookupField = {
        id: 2,
        name: 'Lookup',
        type: 'formula',
        formula_type: 'array',
        array_formula_type: 'text',
      }
      const existingRows = [
        {
          id: 1,
          order: '1.00000000000000000000',
          field_2: [{ id: 20, value: 'Alpha' }],
        },
        {
          id: 3,
          order: '3.00000000000000000000',
          field_2: [{ id: 10, value: 'Beta' }],
        },
        {
          id: 4,
          order: '4.00000000000000000000',
          field_2: [{ id: 30, value: 'Gamma' }],
        },
      ]
      const newRow = {
        id: 99,
        order: '2.50000000000000000000',
        field_2: [{ id: 20, value: 'Alpha' }],
      }
      const position = computeRowInsertPosition(
        newRow,
        existingRows,
        [{ field: 2, order: 'ASC', type: 'default' }],
        [lookupField],
        store.$registry
      )
      expect(position.sortedIndex).toBe(1)
      expect(position.anchorRowId).toBe(1)
    })
  })

  describe('buildNewRowDefaults', () => {
    const field = (id) => ({ id, name: `f${id}`, type: 'text' })
    const makeRegistry = (overrides = {}) => ({
      get() {
        return {
          getNewRowValue: () => 'field_default',
          getSupportedDefaultValueFunctions: () => [],
          parseDefaultRowValue: (_field, value) => `parsed:${value}`,
          resolveDefaultValueFunction: (fn) => `resolved:${fn}`,
          ...overrides,
        }
      },
    })

    test('no view defaults -> getNewRowValue for each field', () => {
      expect(
        buildNewRowDefaults({
          view: { default_row_values: [] },
          fields: [field(1), field(2)],
          registry: makeRegistry(),
        })
      ).toEqual({ field_1: 'field_default', field_2: 'field_default' })
    })

    test('suppliedValues take priority over defaults', () => {
      const result = buildNewRowDefaults({
        view: { default_row_values: [] },
        fields: [field(1), field(2)],
        registry: makeRegistry(),
        suppliedValues: { field_1: 'supplied' },
      })
      expect(result.field_1).toBe('supplied')
      expect(result.field_2).toBe('field_default')
    })

    test('view default value with matching field_type -> parseDefaultRowValue result', () => {
      expect(
        buildNewRowDefaults({
          view: {
            default_row_values: [
              {
                field: 1,
                enabled: true,
                value: 'hello',
                field_type: 'text',
                function: null,
              },
            ],
          },
          fields: [field(1)],
          registry: makeRegistry(),
        })
      ).toEqual({ field_1: 'parsed:hello' })
    })

    test('view default with supported function -> resolveDefaultValueFunction result', () => {
      expect(
        buildNewRowDefaults({
          view: {
            default_row_values: [
              {
                field: 1,
                enabled: true,
                value: null,
                function: 'today',
                field_type: null,
              },
            ],
          },
          fields: [field(1)],
          registry: makeRegistry({
            getSupportedDefaultValueFunctions: () => [{ name: 'today' }],
          }),
        })
      ).toEqual({ field_1: 'resolved:today' })
    })

    test('disabled default -> ignored, falls back to getNewRowValue', () => {
      expect(
        buildNewRowDefaults({
          view: {
            default_row_values: [
              {
                field: 1,
                enabled: false,
                value: 'ignored',
                field_type: 'text',
                function: null,
              },
            ],
          },
          fields: [field(1)],
          registry: makeRegistry(),
        })
      ).toEqual({ field_1: 'field_default' })
    })

    test('view default with mismatched field_type -> falls back to getNewRowValue', () => {
      expect(
        buildNewRowDefaults({
          view: {
            default_row_values: [
              {
                field: 1,
                enabled: true,
                value: 'x',
                field_type: 'number',
                function: null,
              },
            ],
          },
          fields: [field(1)], // type: 'text', not 'number'
          registry: makeRegistry(),
        })
      ).toEqual({ field_1: 'field_default' })
    })
  })

  describe('computeRowInsertPosition', () => {
    const makeSortRegistry = () => ({
      get: (_, type) =>
        type === 'text'
          ? {
              getSortTypes: () => ({
                default: {
                  function: (fieldName, order) => (a, b) => {
                    const va = a[fieldName]
                    const vb = b[fieldName]
                    const cmp = va < vb ? -1 : va > vb ? 1 : 0
                    return order === 'DESC' ? -cmp : cmp
                  },
                },
              }),
            }
          : {},
    })
    const textField = { id: 1, type: 'text' }
    const ascSort = [{ field: 1, order: 'ASC', type: 'default' }]

    const row = (id, val) => ({ id, order: '0', field_1: val })

    test('row sorts first returns anchorRowId null and isFirst true', () => {
      const result = computeRowInsertPosition(
        row(10, 'A'),
        [row(1, 'B'), row(2, 'C')],
        ascSort,
        [textField],
        makeSortRegistry()
      )
      expect(result).toEqual({
        anchorRowId: null,
        sortedIndex: 0,
        isFirst: true,
        isLast: false,
      })
    })

    test('row sorts last returns correct anchorRowId and isLast true', () => {
      const result = computeRowInsertPosition(
        row(10, 'Z'),
        [row(1, 'A'), row(2, 'M')],
        ascSort,
        [textField],
        makeSortRegistry()
      )
      expect(result).toEqual({
        anchorRowId: 2,
        sortedIndex: 2,
        isFirst: false,
        isLast: true,
      })
    })

    test('row sorts in the middle returns correct anchorRowId and index', () => {
      const result = computeRowInsertPosition(
        row(10, 'M'),
        [row(1, 'A'), row(2, 'Z')],
        ascSort,
        [textField],
        makeSortRegistry()
      )
      expect(result).toEqual({
        anchorRowId: 1,
        sortedIndex: 1,
        isFirst: false,
        isLast: false,
      })
    })

    test('empty existing rows makes the new row both first and last', () => {
      const result = computeRowInsertPosition(
        row(10, 'X'),
        [],
        ascSort,
        [textField],
        makeSortRegistry()
      )
      expect(result).toEqual({
        anchorRowId: null,
        sortedIndex: 0,
        isFirst: true,
        isLast: true,
      })
    })

    test('group bys are applied before sortings when computing row position', () => {
      const groupField = { id: 2, type: 'text' }
      const groupedRow = (id, name, group) => ({
        id,
        order: '0',
        field_1: name,
        field_2: group,
      })

      const result = computeRowInsertPosition(
        groupedRow(10, 'M', 'A'),
        [groupedRow(1, 'A', 'B'), groupedRow(2, 'Z', 'A')],
        ascSort,
        [textField, groupField],
        makeSortRegistry(),
        [{ field: 2, order: 'ASC', type: 'default' }]
      )

      expect(result).toEqual({
        anchorRowId: null,
        sortedIndex: 0,
        isFirst: true,
        isLast: false,
      })
    })
  })

  test('extractRowReadOnlyValues', () => {
    const row = {
      id: 1,
      field_2: '2024-01-04T15:15:59.163126Z',
      field_3: 'Text',
    }
    const allFields = [
      {
        id: 2,
        name: 'Last modified',
        type: 'last_modified',
        date_include_time: true,
      },
      {
        id: 3,
        name: 'Text',
        type: 'text',
      },
    ]

    const newRow = extractRowReadOnlyValues(row, allFields, store.$registry)

    expect(newRow).toEqual({
      id: 1,
      field_2: '2024-01-04T15:15:59.163126Z',
    })
  })
})
