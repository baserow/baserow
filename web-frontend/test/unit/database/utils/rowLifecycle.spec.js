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
      { field_1: 'prepared:A' },
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
        { id: 1, field_1: 'A' },
        { id: 2, field_1: 'B' },
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
      row: { id: 1, field_1: 'A' },
    })

    expect(mutations.applyMatchFlags).toHaveBeenCalledWith(1, {
      matchFilters: true,
      matchSortings: true,
    })
  })

  test('marks matchSortings false when the row is not at its sort position', () => {
    const mutations = baseMutations({
      rowsForMatchCheck: vi.fn(() => [
        { id: 2, field_1: 'Z' },
        { id: 99, field_1: 'A' },
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
      row: { id: 99, field_1: 'A' },
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
