/**
 * Tests for the shared row-lifecycle helpers. The helpers own the common
 * create / update / delete / re-evaluate-flags flows, while each grid store
 * supplies its own row mutations.
 */
import { vi } from 'vitest'
import {
  createRowLifecycle,
  createRowLifecycleContext,
  createRowOptimistically,
  updateRowOptimistically,
  deleteRowOptimistically,
  reapplyMatchFlags,
  handleRowCreated,
  handleRowDeleted,
  handleRowUpdated,
} from '@baserow/modules/database/utils/rowLifecycle'

const textField = (id, extra = {}) => ({
  id,
  name: `f${id}`,
  type: 'text',
  ...extra,
})

const stubRegistry = {
  get() {
    return {
      isEqual: (_field, a, b) => JSON.stringify(a) === JSON.stringify(b),
      onRowChange: (_row, _field, value) => value,
      prepareValueForUpdate: (_field, value) => value,
      canWriteFieldValues: () => true,
      getNewRowValue: () => '',
      getSupportedDefaultValueFunctions: () => [],
      parseDefaultRowValue: (_field, value) => value,
      getSortTypes: () => ({
        default: {
          function: (fieldName, order) => (a, b) => {
            const av = a[fieldName]
            const bv = b[fieldName]
            const cmp = av < bv ? -1 : av > bv ? 1 : 0
            return order === 'DESC' ? -cmp : cmp
          },
        },
      }),
    }
  },
}

const registryWithPreparedValues = {
  get() {
    return {
      ...stubRegistry.get(),
      prepareValueForUpdate: (_field, value) => `prepared:${value}`,
    }
  },
}

const baseContext = (overrides = {}) =>
  createRowLifecycleContext({
    client: {},
    registry: stubRegistry,
    table: { id: 99 },
    view: {
      id: 7,
      sortings: [],
      filters: [],
      filter_groups: [],
      filters_disabled: true,
      filter_type: 'AND',
      default_row_values: [],
    },
    fields: [textField(1), textField(2)],
    rowService: {},
    ...overrides,
  })

const baseMutations = (overrides = {}) => ({
  insert: vi.fn(),
  replace: vi.fn(),
  remove: vi.fn(),
  applyValues: vi.fn(),
  applyMatchFlags: vi.fn(),
  rowsForMatchCheck: vi.fn(() => []),
  ...overrides,
})

beforeEach(() => {
  vi.clearAllMocks()
})

describe('rowLifecycle / createRowOptimistically', () => {
  test('happy path: insert -> POST -> replace -> applyMatchFlags', async () => {
    const calls = []
    const beRow = { id: 42, field_1: 'A', field_2: 'be-default' }
    const service = {
      create: vi.fn().mockResolvedValue({ data: beRow }),
    }
    const mutations = baseMutations({
      insert: vi.fn((row, tempId) =>
        calls.push(['insert', tempId, row.field_1])
      ),
      replace: vi.fn((tempId, row) => calls.push(['replace', tempId, row.id])),
      remove: vi.fn(() => calls.push(['remove'])),
      applyMatchFlags: vi.fn((id, flags) => calls.push(['flags', id, flags])),
      rowsForMatchCheck: vi.fn(() => [beRow]),
    })
    const selectCell = vi.fn()

    const result = await createRowOptimistically({
      context: baseContext({
        registry: registryWithPreparedValues,
        rowService: service,
        fields: [textField(1, { primary: true }), textField(2)],
      }),
      mutations,
      beforeId: 24,
      suppliedValues: { field_1: 'A' },
      selection: {
        selectPrimaryCell: true,
        selectCell,
      },
    })

    expect(result).toMatchObject({ id: 42, field_1: 'A' })
    expect(mutations.insert).toHaveBeenCalledTimes(1)
    expect(mutations.insert.mock.calls[0][0]).toMatchObject({
      field_1: 'A',
      field_2: '',
      _: { loading: true },
    })
    expect(mutations.insert.mock.calls[0][0].id).toBeLessThan(0)
    expect(service.create).toHaveBeenCalledWith(
      99,
      { field_1: 'prepared:A', field_2: 'prepared:' },
      24,
      7
    )
    expect(mutations.replace).toHaveBeenCalledTimes(1)
    expect(mutations.remove).not.toHaveBeenCalled()
    expect(mutations.rowsForMatchCheck).toHaveBeenCalledWith(beRow)
    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(42, {
      matchFilters: true,
      matchSortings: true,
    })
    expect(selectCell).toHaveBeenCalledWith(42, 1)
    expect(calls.map((call) => call[0])).toEqual(['insert', 'replace', 'flags'])
    expect(calls[1][1]).toBe(calls[0][1])
    expect(calls[2][1]).toBe(42)
  })

  test('BE failure: insert -> POST throws -> remove -> re-throw', async () => {
    const mutations = baseMutations()
    const service = {
      create: vi.fn().mockRejectedValue(new Error('BE down')),
    }

    await expect(
      createRowOptimistically({
        context: baseContext({ rowService: service }),
        mutations,
        suppliedValues: { field_1: 'A' },
      })
    ).rejects.toThrow('BE down')

    expect(mutations.insert).toHaveBeenCalledTimes(1)
    expect(mutations.remove).toHaveBeenCalledWith(
      mutations.insert.mock.calls[0][1]
    )
    expect(mutations.replace).not.toHaveBeenCalled()
  })

  test('BE returns null data: removes optimistic row and returns null', async () => {
    const mutations = baseMutations()
    const service = {
      create: vi.fn().mockResolvedValue({ data: null }),
    }

    const result = await createRowOptimistically({
      context: baseContext({ rowService: service }),
      mutations,
      suppliedValues: { field_1: 'A' },
    })

    expect(result).toBeNull()
    expect(mutations.insert).toHaveBeenCalled()
    expect(mutations.replace).not.toHaveBeenCalled()
    expect(mutations.applyMatchFlags).not.toHaveBeenCalled()
    expect(mutations.remove).toHaveBeenCalledWith(
      mutations.insert.mock.calls[0][1]
    )
  })

  test('view default row values are included in the create request', async () => {
    const beRow = { id: 42, field_1: 'Default name' }
    const service = {
      create: vi.fn().mockResolvedValue({ data: beRow }),
    }
    const mutations = baseMutations({
      rowsForMatchCheck: vi.fn(() => [beRow]),
    })

    await createRowOptimistically({
      context: baseContext({
        registry: registryWithPreparedValues,
        rowService: service,
        view: {
          id: 7,
          sortings: [],
          filters: [],
          filter_groups: [],
          filters_disabled: true,
          filter_type: 'AND',
          default_row_values: [
            {
              field: 1,
              enabled: true,
              value: 'Default name',
              field_type: 'text',
              function: null,
            },
          ],
        },
        fields: [textField(1)],
      }),
      mutations,
    })

    expect(mutations.insert.mock.calls[0][0]).toMatchObject({
      field_1: 'Default name',
      _: { loading: true },
    })
    expect(service.create).toHaveBeenCalledWith(
      99,
      { field_1: 'prepared:Default name' },
      null,
      7
    )
  })

  test('non-writable fields are not included in the create request', async () => {
    const service = {
      create: vi.fn().mockResolvedValue({
        data: { id: 42, field_1: 'A', field_2: 'Readonly' },
      }),
    }
    const registry = {
      get(_type, name) {
        return {
          ...registryWithPreparedValues.get(),
          canWriteFieldValues: () => name !== 'formula',
        }
      },
    }

    await createRowOptimistically({
      context: baseContext({
        registry,
        rowService: service,
        fields: [textField(1), textField(2, { type: 'formula' })],
      }),
      mutations: baseMutations(),
      suppliedValues: { field_1: 'A', field_2: 'Readonly' },
    })

    expect(service.create).toHaveBeenCalledWith(
      99,
      { field_1: 'prepared:A' },
      null,
      7
    )
  })
})

describe('rowLifecycle / updateRowOptimistically', () => {
  const buildRow = () => ({ id: 5, field_1: 'old', field_2: 'unchanged' })

  test('happy path: optimistic write -> PATCH -> write BE response -> flags', async () => {
    const calls = []
    const beRow = { id: 5, field_1: 'new', field_2: 'unchanged' }
    const service = {
      batchUpdate: vi.fn().mockResolvedValue({
        data: { items: [beRow] },
      }),
    }
    const mutations = baseMutations({
      applyValues: vi.fn((id, values) =>
        calls.push(['applyValues', id, values.field_1])
      ),
      applyMatchFlags: vi.fn((id, flags) => calls.push(['flags', id, flags])),
      rowsForMatchCheck: vi.fn(() => [beRow]),
    })

    await updateRowOptimistically({
      context: baseContext({
        registry: registryWithPreparedValues,
        rowService: service,
      }),
      mutations,
      edit: {
        row: buildRow(),
        field: textField(1),
        value: 'new',
        oldValue: 'old',
      },
    })

    expect(mutations.applyValues).toHaveBeenCalledTimes(2)
    expect(calls[0]).toEqual(['applyValues', 5, 'new'])
    expect(calls[1][0]).toBe('applyValues')
    expect(service.batchUpdate).toHaveBeenCalledWith(
      99,
      [{ id: 5, field_1: 'prepared:new' }],
      null,
      7
    )
    expect(mutations.rowsForMatchCheck).toHaveBeenCalledWith(beRow)
    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(5, {
      matchFilters: true,
      matchSortings: true,
    })
  })

  test('BE failure: writes optimistic -> BE fails -> reverts to oldValue -> throws', async () => {
    const seen = []
    const service = {
      batchUpdate: vi.fn().mockRejectedValue(new Error('BE down')),
    }
    const mutations = baseMutations({
      applyValues: vi.fn((_id, values) => seen.push(values.field_1)),
    })

    await expect(
      updateRowOptimistically({
        context: baseContext({ rowService: service }),
        mutations,
        edit: {
          row: buildRow(),
          field: textField(1),
          value: 'new',
          oldValue: 'old',
        },
      })
    ).rejects.toThrow('BE down')

    expect(seen).toEqual(['new', 'old'])
  })
})

describe('rowLifecycle / deleteRowOptimistically', () => {
  test('happy path: remove -> DELETE -> return true', async () => {
    const mutations = baseMutations()
    const service = {
      delete: vi.fn().mockResolvedValue({}),
    }

    const result = await deleteRowOptimistically({
      context: baseContext({ rowService: service }),
      mutations,
      row: { id: 5, field_1: 'A' },
    })

    expect(result).toBe(true)
    expect(mutations.remove).toHaveBeenCalledWith(5)
    expect(service.delete).toHaveBeenCalledWith(99, 5, 7)
    expect(mutations.insert).not.toHaveBeenCalled()
  })

  test('BE failure: remove -> DELETE throws -> re-insert original -> re-throw', async () => {
    const row = { id: 5, field_1: 'A' }
    const mutations = baseMutations()
    const service = {
      delete: vi.fn().mockRejectedValue(new Error('BE down')),
    }

    await expect(
      deleteRowOptimistically({
        context: baseContext({ rowService: service }),
        mutations,
        row,
      })
    ).rejects.toThrow('BE down')

    expect(mutations.remove).toHaveBeenCalledWith(5)
    expect(service.delete).toHaveBeenCalledWith(99, 5, 7)
    expect(mutations.insert).toHaveBeenCalledWith(row, 5)
  })

  test('missing row: no-op, returns false', async () => {
    const mutations = baseMutations()

    const result = await deleteRowOptimistically({
      context: baseContext(),
      mutations,
      row: null,
    })

    expect(result).toBe(false)
    expect(mutations.remove).not.toHaveBeenCalled()
  })
})

describe('rowLifecycle / reapplyMatchFlags', () => {
  test('computes flags via matchSearchFilters + sort, applies via callback', () => {
    const mutations = baseMutations({
      rowsForMatchCheck: vi.fn(() => [
        { id: 1, field_1: 'A', order: '0' },
        { id: 2, field_1: 'B', order: '0' },
      ]),
    })

    reapplyMatchFlags({
      context: baseContext({
        view: {
          filters_disabled: true,
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        },
        fields: [textField(1)],
      }),
      mutations,
      row: { id: 1, field_1: 'A', order: '0' },
    })

    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(1, {
      matchFilters: true,
      matchSortings: true,
    })
  })

  test('marks matchSortings false when the row is not at its sort position', () => {
    const mutations = baseMutations({
      rowsForMatchCheck: vi.fn(() => [
        { id: 2, field_1: 'Z', order: '0' },
        { id: 99, field_1: 'A', order: '0' },
      ]),
    })

    reapplyMatchFlags({
      context: baseContext({
        view: {
          filters_disabled: true,
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        },
        fields: [textField(1)],
      }),
      mutations,
      row: { id: 99, field_1: 'A', order: '0' },
    })

    const [, flags] = mutations.applyMatchFlags.mock.calls[0]
    expect(flags.matchSortings).toBe(false)
  })

  test('null row: no-op', () => {
    const mutations = baseMutations()

    reapplyMatchFlags({
      context: baseContext(),
      mutations,
      row: null,
    })

    expect(mutations.applyMatchFlags).not.toHaveBeenCalled()
  })
})

describe('handleRowCreated', () => {
  const row = { id: 10, field_1: 'new', order: '0' }

  test('row matches view: inserts at computed position and applies flags', () => {
    const existingRows = [
      { id: 1, field_1: 'A', order: '0' },
      { id: 2, field_1: 'Z', order: '0' },
    ]
    const mutations = baseMutations({
      insertAtPosition: vi.fn(),
      rowsForMatchCheck: vi.fn(() => existingRows),
    })

    handleRowCreated({
      context: baseContext({
        view: {
          filters_disabled: true,
          sortings: [{ field: 1, order: 'ASC', type: 'default' }],
          filters: [],
          filter_groups: [],
          filter_type: 'AND',
          default_row_values: [],
        },
        fields: [textField(1)],
      }),
      mutations,
      row,
    })

    expect(mutations.insertAtPosition).toHaveBeenCalledTimes(1)
    const [insertedRow, position] = mutations.insertAtPosition.mock.calls[0]
    expect(insertedRow).toBe(row)
    // Lexicographic ASC: 'A' < 'Z' < 'new' (lowercase 'n' > uppercase 'Z' in Unicode)
    // so 'new' lands at index 2, after 'Z' (id=2)
    expect(position.sortedIndex).toBe(2)
    expect(position.anchorRowId).toBe(2)
    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(10, {
      matchFilters: true,
      matchSortings: true,
    })
  })

  test("row doesn't match filters: returns without inserting", () => {
    // Registry that handles viewFilter types so matchSearchFilters can
    // evaluate the 'equal' filter and return false.
    const registryWithFilterType = {
      get(type, name) {
        if (type === 'viewFilter') {
          return {
            matches: (_rowValue, _filterValue, _field, _fieldType) => false,
          }
        }
        return stubRegistry.get()
      },
    }
    const mutations = baseMutations({
      insertAtPosition: vi.fn(),
      rowsForMatchCheck: vi.fn(() => []),
    })

    handleRowCreated({
      context: baseContext({
        registry: registryWithFilterType,
        view: {
          filters_disabled: false,
          sortings: [],
          filters: [
            { field: 1, type: 'equal', value: 'other', preload_values: {} },
          ],
          filter_groups: [],
          filter_type: 'AND',
          default_row_values: [],
        },
        fields: [textField(1)],
      }),
      mutations,
      row,
    })

    expect(mutations.insertAtPosition).not.toHaveBeenCalled()
    expect(mutations.applyMatchFlags).not.toHaveBeenCalled()
  })

  test('rowsForMatchCheck absent: falls back to empty rows', () => {
    const { rowsForMatchCheck: _omitted, ...mutationsWithoutRows } =
      baseMutations()
    const mutations = { ...mutationsWithoutRows, insertAtPosition: vi.fn() }

    handleRowCreated({
      context: baseContext(),
      mutations,
      row,
    })

    expect(mutations.insertAtPosition).toHaveBeenCalledTimes(1)
    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(10, {
      matchFilters: true,
      matchSortings: true,
    })
  })
})

describe('handleRowDeleted', () => {
  const row = { id: 10, field_1: 'gone' }

  test('row was visible: remove is called', () => {
    const mutations = baseMutations()

    handleRowDeleted({
      context: baseContext(),
      mutations,
      row,
    })

    expect(mutations.remove).toHaveBeenCalledWith(10)
  })

  test('row did not match filters: remove is not called', () => {
    const registryWithFilterType = {
      get(type) {
        if (type === 'viewFilter') {
          return { matches: () => false }
        }
        return stubRegistry.get()
      },
    }
    const mutations = baseMutations()

    handleRowDeleted({
      context: baseContext({
        registry: registryWithFilterType,
        view: {
          filters_disabled: false,
          sortings: [],
          filters: [
            { field: 1, type: 'equal', value: 'other', preload_values: {} },
          ],
          filter_groups: [],
          filter_type: 'AND',
          default_row_values: [],
        },
        fields: [textField(1)],
      }),
      mutations,
      row,
    })

    expect(mutations.remove).not.toHaveBeenCalled()
  })

  test('rowsForMatchCheck absent: falls back to empty rows, still removes', () => {
    const { rowsForMatchCheck: _omitted, ...mutationsWithoutRows } =
      baseMutations()

    handleRowDeleted({
      context: baseContext(),
      mutations: mutationsWithoutRows,
      row,
    })

    expect(mutationsWithoutRows.remove).toHaveBeenCalledWith(10)
  })
})

describe('handleRowUpdated', () => {
  // A view context with ASC sorting on field_1 so position assertions are concrete.
  const sortedView = {
    filters_disabled: true,
    sortings: [{ field: 1, order: 'ASC', type: 'default' }],
    filters: [],
    filter_groups: [],
    filter_type: 'AND',
    default_row_values: [],
  }

  test('old in view, new NOT in view: remove(newRow.id)', () => {
    // Use a value-aware filter registry.
    const registryValueAware = {
      get(type) {
        if (type === 'viewFilter') {
          // matches only when value === 'keep'
          return { matches: (rowValue) => rowValue === 'keep' }
        }
        return stubRegistry.get()
      },
    }
    const viewWithFilter = {
      filters_disabled: false,
      sortings: [],
      filters: [{ field: 1, type: 'equal', value: 'keep', preload_values: {} }],
      filter_groups: [],
      filter_type: 'AND',
      default_row_values: [],
    }
    const oldRow = { id: 5, field_1: 'keep' } // was in view
    const newRow = { id: 5, field_1: 'gone' } // no longer in view
    const mutations = {
      ...baseMutations(),
      insertAtPosition: vi.fn(),
      replaceAtPosition: vi.fn(),
    }

    handleRowUpdated({
      context: baseContext({
        registry: registryValueAware,
        view: viewWithFilter,
        fields: [textField(1)],
      }),
      mutations,
      oldRow,
      newRow,
    })

    expect(mutations.remove).toHaveBeenCalledWith(5)
    expect(mutations.insertAtPosition).not.toHaveBeenCalled()
    expect(mutations.replaceAtPosition).not.toHaveBeenCalled()
    expect(mutations.applyMatchFlags).not.toHaveBeenCalled()
  })

  test('old NOT in view, new in view: insertAtPosition + applyMatchFlags', () => {
    const registryValueAware = {
      get(type) {
        if (type === 'viewFilter') {
          return { matches: (rowValue) => rowValue === 'keep' }
        }
        return stubRegistry.get()
      },
    }
    const viewWithFilter = {
      filters_disabled: false,
      sortings: [{ field: 1, order: 'ASC', type: 'default' }],
      filters: [{ field: 1, type: 'equal', value: 'keep', preload_values: {} }],
      filter_groups: [],
      filter_type: 'AND',
      default_row_values: [],
    }
    const oldRow = { id: 5, field_1: 'gone', order: '0' } // was NOT in view (filter: 'gone' !== 'keep')
    const newRow = { id: 5, field_1: 'keep', order: '0' } // now in view; 'keep' sorts between 'alpha' and 'zebra'
    // ASC: 'alpha' < 'keep' < 'zebra', so newRow inserts at index 1, after id=1
    const existingRows = [
      { id: 1, field_1: 'alpha', order: '0' },
      { id: 2, field_1: 'zebra', order: '0' },
    ]
    const mutations = {
      ...baseMutations({
        rowsForMatchCheck: vi.fn(() => existingRows),
      }),
      insertAtPosition: vi.fn(),
      replaceAtPosition: vi.fn(),
    }

    handleRowUpdated({
      context: baseContext({
        registry: registryValueAware,
        view: viewWithFilter,
        fields: [textField(1)],
      }),
      mutations,
      oldRow,
      newRow,
    })

    expect(mutations.insertAtPosition).toHaveBeenCalledTimes(1)
    const [insertedRow, position] = mutations.insertAtPosition.mock.calls[0]
    expect(insertedRow).toBe(newRow)
    expect(position.sortedIndex).toBe(1)
    expect(position.anchorRowId).toBe(1)
    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(5, {
      matchFilters: true,
      matchSortings: true,
    })
    expect(mutations.remove).not.toHaveBeenCalled()
    expect(mutations.replaceAtPosition).not.toHaveBeenCalled()
  })

  test('old NOT in view, new NOT in view: noop', () => {
    const registryValueAware = {
      get(type) {
        if (type === 'viewFilter') {
          return { matches: (rowValue) => rowValue === 'keep' }
        }
        return stubRegistry.get()
      },
    }
    const viewWithFilter = {
      filters_disabled: false,
      sortings: [],
      filters: [{ field: 1, type: 'equal', value: 'keep', preload_values: {} }],
      filter_groups: [],
      filter_type: 'AND',
      default_row_values: [],
    }
    const oldRow = { id: 5, field_1: 'gone' }
    const newRow = { id: 5, field_1: 'also-gone' }
    const mutations = {
      ...baseMutations(),
      insertAtPosition: vi.fn(),
      replaceAtPosition: vi.fn(),
    }

    handleRowUpdated({
      context: baseContext({
        registry: registryValueAware,
        view: viewWithFilter,
        fields: [textField(1)],
      }),
      mutations,
      oldRow,
      newRow,
    })

    expect(mutations.remove).not.toHaveBeenCalled()
    expect(mutations.insertAtPosition).not.toHaveBeenCalled()
    expect(mutations.replaceAtPosition).not.toHaveBeenCalled()
    expect(mutations.applyMatchFlags).not.toHaveBeenCalled()
  })

  test('old in view, new in view: replaceAtPosition + applyMatchFlags, position excludes self', () => {
    // filters_disabled so both old and new pass
    const existingRows = [
      { id: 1, field_1: 'A', order: '0' },
      { id: 5, field_1: 'B', order: '0' }, // the row being updated — must be excluded from position calc
      { id: 9, field_1: 'Z', order: '0' },
    ]
    const oldRow = { id: 5, field_1: 'B', order: '0' }
    const newRow = { id: 5, field_1: 'M', order: '0' } // moves between A and Z
    const mutations = {
      ...baseMutations({
        rowsForMatchCheck: vi.fn(() => existingRows),
      }),
      insertAtPosition: vi.fn(),
      replaceAtPosition: vi.fn(),
    }

    handleRowUpdated({
      context: baseContext({
        view: sortedView,
        fields: [textField(1)],
      }),
      mutations,
      oldRow,
      newRow,
    })

    expect(mutations.replaceAtPosition).toHaveBeenCalledTimes(1)
    const [rowId, replacedRow, position] =
      mutations.replaceAtPosition.mock.calls[0]
    expect(rowId).toBe(5)
    expect(replacedRow).toBe(newRow)
    // Rows excluding self: [{id:1,'A'}, {id:9,'Z'}].  'M' sorts between 'A' and 'Z' → index 1.
    expect(position.sortedIndex).toBe(1)
    expect(position.anchorRowId).toBe(1)
    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(5, {
      matchFilters: true,
      matchSortings: true,
    })
    expect(mutations.remove).not.toHaveBeenCalled()
    expect(mutations.insertAtPosition).not.toHaveBeenCalled()
  })
})

describe('createRowLifecycle', () => {
  test('returns methods bound to a context and mutation adapter', async () => {
    const mutations = baseMutations()
    const service = {
      delete: vi.fn().mockResolvedValue({}),
    }
    const lifecycle = createRowLifecycle(
      baseContext({ rowService: service }),
      mutations
    )

    await expect(lifecycle.delete({ row: { id: 5 } })).resolves.toBe(true)

    expect(mutations.remove).toHaveBeenCalledWith(5)
    expect(service.delete).toHaveBeenCalledWith(99, 5, 7)
  })
})
