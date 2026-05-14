/**
 * Tests for the shared row-lifecycle helpers. These functions are the
 * canonical create / update / delete / re-evaluate-flags flows; both
 * the grouped grid (today) and the flat grid (in a follow-up PR) call
 * them. Each test exercises one helper with a stub adapter that
 * records calls, so we can assert the exact sequence + arguments the
 * helper drives without standing up a Vuex store.
 */
import { vi } from 'vitest'
import {
  createRowOptimistically,
  updateRowOptimistically,
  deleteRowOptimistically,
  reapplyMatchFlags,
} from '@baserow/modules/database/utils/rowLifecycle'
import RowService from '@baserow/modules/database/services/row'

vi.mock('@baserow/modules/database/services/row', () => ({
  default: vi.fn(),
}))

const textField = (id) => ({ id, name: `f${id}`, type: 'text' })

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

const baseArgs = () => ({
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
})

describe('rowLifecycle / createRowOptimistically', () => {
  test('happy path: insert → POST → replace → applyMatchFlags', async () => {
    const calls = []
    const insert = vi.fn((row, tempId) =>
      calls.push(['insert', tempId, row.field_1])
    )
    const replace = vi.fn((tempId, beRow) =>
      calls.push(['replace', tempId, beRow.id])
    )
    const remove = vi.fn(() => calls.push(['remove']))
    const applyMatchFlags = vi.fn((id, flags) =>
      calls.push(['flags', id, flags])
    )
    const rowsForMatchCheck = vi.fn(() => [{ id: 42, field_1: 'A' }])

    RowService.mockReturnValue({
      create: vi.fn().mockResolvedValue({
        data: { id: 42, field_1: 'A', field_2: 'be-default' },
      }),
    })

    const result = await createRowOptimistically({
      ...baseArgs(),
      suppliedValues: { field_1: 'A' },
      insert,
      replace,
      remove,
      applyMatchFlags,
      rowsForMatchCheck,
    })

    expect(result).toMatchObject({ id: 42, field_1: 'A' })
    expect(insert).toHaveBeenCalledTimes(1)
    expect(replace).toHaveBeenCalledTimes(1)
    expect(remove).not.toHaveBeenCalled()
    expect(applyMatchFlags).toHaveBeenCalledTimes(1)
    // Order: insert → replace → flags.
    expect(calls.map((c) => c[0])).toEqual(['insert', 'replace', 'flags'])
    // Temp id was the same in insert + replace.
    const tempIdInsert = calls[0][1]
    const tempIdReplace = calls[1][1]
    expect(tempIdReplace).toBe(tempIdInsert)
    // applyMatchFlags got the BE id (not temp).
    expect(calls[2][1]).toBe(42)
  })

  test('BE failure: insert → POST throws → remove → re-throw', async () => {
    const insert = vi.fn()
    const replace = vi.fn()
    const remove = vi.fn()
    RowService.mockReturnValue({
      create: vi.fn().mockRejectedValue(new Error('BE down')),
    })

    await expect(
      createRowOptimistically({
        ...baseArgs(),
        suppliedValues: { field_1: 'A' },
        insert,
        replace,
        remove,
      })
    ).rejects.toThrow('BE down')

    expect(insert).toHaveBeenCalledTimes(1)
    expect(remove).toHaveBeenCalledTimes(1)
    expect(replace).not.toHaveBeenCalled()
  })

  test('BE returns null data: insert + no replace + no flags', async () => {
    const insert = vi.fn()
    const replace = vi.fn()
    const remove = vi.fn()
    const applyMatchFlags = vi.fn()
    RowService.mockReturnValue({
      create: vi.fn().mockResolvedValue({ data: null }),
    })

    const result = await createRowOptimistically({
      ...baseArgs(),
      suppliedValues: { field_1: 'A' },
      insert,
      replace,
      remove,
      applyMatchFlags,
    })

    expect(result).toBeNull()
    expect(insert).toHaveBeenCalled()
    expect(replace).not.toHaveBeenCalled()
    expect(applyMatchFlags).not.toHaveBeenCalled()
    expect(remove).not.toHaveBeenCalled()
  })
})

describe('rowLifecycle / updateRowOptimistically', () => {
  const buildRow = () => ({ id: 5, field_1: 'old', field_2: 'unchanged' })

  test('happy path: optimistic write → PATCH → write BE response → flags', async () => {
    const calls = []
    const applyValues = vi.fn((id, values) =>
      calls.push(['applyValues', id, values.field_1])
    )
    const applyMatchFlags = vi.fn((id, flags) =>
      calls.push(['flags', id, flags])
    )
    RowService.mockReturnValue({
      batchUpdate: vi.fn().mockResolvedValue({
        data: { items: [{ id: 5, field_1: 'new', field_2: 'unchanged' }] },
      }),
    })

    await updateRowOptimistically({
      ...baseArgs(),
      row: buildRow(),
      field: textField(1),
      value: 'new',
      oldValue: 'old',
      applyValues,
      applyMatchFlags,
      rowsForMatchCheck: () => [],
    })

    // applyValues called twice: once optimistically, once with BE response.
    expect(applyValues).toHaveBeenCalledTimes(2)
    expect(calls[0]).toEqual(['applyValues', 5, 'new'])
    expect(calls[1][0]).toBe('applyValues') // BE response
    expect(applyMatchFlags).toHaveBeenCalledTimes(1)
  })

  test('BE failure: writes optimistic → BE fails → reverts to oldValue → throws', async () => {
    const seen = []
    const applyValues = vi.fn((id, values) => seen.push(values.field_1))
    RowService.mockReturnValue({
      batchUpdate: vi.fn().mockRejectedValue(new Error('BE down')),
    })

    await expect(
      updateRowOptimistically({
        ...baseArgs(),
        row: buildRow(),
        field: textField(1),
        value: 'new',
        oldValue: 'old',
        applyValues,
        applyMatchFlags: () => {},
      })
    ).rejects.toThrow('BE down')

    // First call wrote 'new'; second call (rollback) wrote 'old'.
    expect(seen).toEqual(['new', 'old'])
  })
})

describe('rowLifecycle / deleteRowOptimistically', () => {
  test('happy path: remove → DELETE → return true', async () => {
    const remove = vi.fn()
    const insert = vi.fn()
    RowService.mockReturnValue({
      delete: vi.fn().mockResolvedValue({}),
    })
    const result = await deleteRowOptimistically({
      client: {},
      table: { id: 99 },
      row: { id: 5, field_1: 'A' },
      remove,
      insert,
    })
    expect(result).toBe(true)
    expect(remove).toHaveBeenCalledWith(5)
    expect(insert).not.toHaveBeenCalled()
  })

  test('BE failure: remove → DELETE throws → re-insert original → re-throw', async () => {
    const remove = vi.fn()
    const insert = vi.fn()
    RowService.mockReturnValue({
      delete: vi.fn().mockRejectedValue(new Error('BE down')),
    })
    const row = { id: 5, field_1: 'A' }
    await expect(
      deleteRowOptimistically({
        client: {},
        table: { id: 99 },
        row,
        remove,
        insert,
      })
    ).rejects.toThrow('BE down')
    expect(remove).toHaveBeenCalledWith(5)
    expect(insert).toHaveBeenCalledWith(row, 5)
  })

  test('missing row: no-op, returns false', async () => {
    const remove = vi.fn()
    const result = await deleteRowOptimistically({
      client: {},
      table: { id: 99 },
      row: null,
      remove,
      insert: vi.fn(),
    })
    expect(result).toBe(false)
    expect(remove).not.toHaveBeenCalled()
  })
})

describe('rowLifecycle / reapplyMatchFlags', () => {
  test('computes flags via matchSearchFilters + sort, applies via callback', () => {
    const applyMatchFlags = vi.fn()
    reapplyMatchFlags({
      registry: stubRegistry,
      row: { id: 1, field_1: 'A' },
      view: {
        filters_disabled: true,
        sortings: [{ field: 1, order: 'ASC', type: 'default' }],
      },
      fields: [textField(1)],
      applyMatchFlags,
      rowsForMatchCheck: () => [
        { id: 1, field_1: 'A' },
        { id: 2, field_1: 'B' },
      ],
    })
    expect(applyMatchFlags).toHaveBeenCalledTimes(1)
    const [rowId, flags] = applyMatchFlags.mock.calls[0]
    expect(rowId).toBe(1)
    expect(flags.matchFilters).toBe(true)
    expect(flags.matchSortings).toBe(true)
  })

  test('marks matchSortings false when the row is not at its sort position', () => {
    const applyMatchFlags = vi.fn()
    reapplyMatchFlags({
      registry: stubRegistry,
      row: { id: 99, field_1: 'A' },
      view: {
        filters_disabled: true,
        sortings: [{ field: 1, order: 'ASC', type: 'default' }],
      },
      fields: [textField(1)],
      applyMatchFlags,
      rowsForMatchCheck: () => [
        // Current order: row 99 (A) is at index 0; row 2 (Z) at 1.
        // Sorted ASC: same — row 99 (A) first, row 2 (Z) second. So
        // matchSortings = true. Flip: put 99 at index 1 instead.
        { id: 2, field_1: 'Z' },
        { id: 99, field_1: 'A' },
      ],
    })
    const [, flags] = applyMatchFlags.mock.calls[0]
    expect(flags.matchSortings).toBe(false)
  })

  test('null row: no-op', () => {
    const applyMatchFlags = vi.fn()
    reapplyMatchFlags({
      registry: stubRegistry,
      row: null,
      view: {},
      fields: [],
      applyMatchFlags,
    })
    expect(applyMatchFlags).not.toHaveBeenCalled()
  })
})
