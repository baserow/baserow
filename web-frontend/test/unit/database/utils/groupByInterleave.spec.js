import { describe, expect, it } from 'vitest'

import {
  buildHeightIndex,
  buildInterleavedList,
  COLLAPSED_GROUPS_MODE_COLLAPSE,
  findDepth0GroupPosition,
  GROUP_HEADER_HEIGHT,
  GROUP_ROW_HEIGHT,
  resolveScrollTop,
  rowOffsetToY,
} from '@baserow/modules/database/utils/groupByInterleave'

const mockRegistry = {
  get() {
    return {
      isEqual(field, a, b) {
        return JSON.stringify(a) === JSON.stringify(b)
      },
      getRowValueFromGroupValue(field, value) {
        return value
      },
    }
  },
}

describe('buildInterleavedList', () => {
  it('returns only rows when no group-bys are active', () => {
    const rows = [
      { id: 1, field_1: 'A' },
      { id: 2, field_1: 'B' },
    ]

    expect(
      buildInterleavedList({
        rows,
        activeGroupBys: [],
        groupByMetadata: {},
        collapsedGroups: [],
        registry: mockRegistry,
      })
    ).toEqual([
      { type: 'row', row: rows[0] },
      { type: 'row', row: rows[1] },
    ])
  })

  it('interleaves headers for a single group-by', () => {
    const field = { id: 1, type: 'text' }
    const rows = [
      { id: 1, field_1: 'A' },
      { id: 2, field_1: 'A' },
      { id: 3, field_1: 'B' },
    ]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
      },
      collapsedGroups: [],
      registry: mockRegistry,
      fields: [field],
    })

    expect(result).toEqual([
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'A' },
        count: 2,
        collapsed: false,
      },
      { type: 'row', row: rows[0] },
      { type: 'row', row: rows[1] },
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'B' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[2] },
    ])
  })

  it('skips every row of a collapsed group, not just the first', () => {
    const field = { id: 1, type: 'text' }
    const rows = [
      { id: 1, field_1: 'A' },
      { id: 2, field_1: 'A' },
      { id: 3, field_1: 'B' },
    ]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
      },
      collapsedGroups: [{ field_1: 'A' }],
      registry: mockRegistry,
      fields: [field],
    })

    const visibleRowIds = result
      .filter((item) => item.type === 'row')
      .map((item) => item.row.id)
    expect(visibleRowIds).toEqual([3])
  })

  it('marks collapsed groups and inserts missing collapsed headers', () => {
    const field = { id: 1, type: 'text' }
    const rows = [{ id: 3, field_1: 'B' }]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
      },
      collapsedGroups: [{ field_1: 'A' }],
      registry: mockRegistry,
      fields: [field],
    })

    expect(result).toEqual([
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'A' },
        count: 2,
        collapsed: true,
      },
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 'B' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[0] },
    ])
  })

  it('does not insert collapsed depth-0 headers that are outside the current buffer', () => {
    const field = { id: 1, type: 'text' }
    const rows = [
      { id: 3, field_1: 'B' },
      { id: 4, field_1: 'B' },
    ]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 10 },
        ],
      },
      collapsedGroups: [{ field_1: 'A' }],
      registry: mockRegistry,
      fields: [field],
      bufferStartIndex: 5,
    })

    expect(result).toEqual([
      { type: 'row', row: rows[0] },
      { type: 'row', row: rows[1] },
    ])
  })

  it('keeps collapsed depth-0 sibling headers visible in collapse mode', () => {
    const category = { id: 1, type: 'text' }
    const completed = { id: 2, type: 'boolean' }

    const result = buildInterleavedList({
      rows: [],
      activeGroupBys: [
        { field: 1, order: 'ASC' },
        { field: 2, order: 'ASC' },
      ],
      groupByMetadata: {
        field_1: [
          { field_1: 'Accounting', count: 1383 },
          { field_1: 'Design', count: 2 },
          { field_1: 'Development', count: 4805 },
        ],
        field_2: [
          { field_1: 'Accounting', field_2: false, count: 689 },
          { field_1: 'Accounting', field_2: true, count: 694 },
        ],
      },
      collapsedGroups: [{ field_1: 'Accounting' }],
      collapsedGroupsMode: COLLAPSED_GROUPS_MODE_COLLAPSE,
      registry: mockRegistry,
      fields: [category, completed],
      bufferStartIndex: 1000,
    })

    expect(
      result
        .filter((item) => item.type === 'header')
        .map((item) => ({
          depth: item.depth,
          groupValues: item.groupValues,
          collapsed: item.collapsed,
        }))
    ).toEqual([
      {
        depth: 0,
        groupValues: { field_1: 'Accounting' },
        collapsed: false,
      },
      {
        depth: 1,
        groupValues: { field_1: 'Accounting', field_2: false },
        collapsed: true,
      },
      {
        depth: 1,
        groupValues: { field_1: 'Accounting', field_2: true },
        collapsed: true,
      },
      {
        depth: 0,
        groupValues: { field_1: 'Design' },
        collapsed: true,
      },
      {
        depth: 0,
        groupValues: { field_1: 'Development' },
        collapsed: true,
      },
    ])
  })

  it('does not render group headers for a buffer starting in the middle of a group', () => {
    const field = { id: 1, type: 'text' }
    const rows = [
      { id: 20, field_1: 'B' },
      { id: 21, field_1: 'B' },
    ]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 10 },
        ],
      },
      collapsedGroups: [],
      registry: mockRegistry,
      fields: [field],
      bufferStartIndex: 5,
    })

    expect(result).toEqual([
      { type: 'row', row: rows[0] },
      { type: 'row', row: rows[1] },
    ])
  })

  it('renders child headers when a buffer starts exactly at a nested group boundary', () => {
    const category = { id: 1, type: 'text' }
    const completed = { id: 2, type: 'boolean' }
    const rows = [
      { id: 20, field_1: 'B', field_2: true },
      { id: 21, field_1: 'B', field_2: true },
    ]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [
        { field: 1, order: 'ASC' },
        { field: 2, order: 'ASC' },
      ],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 10 },
        ],
        field_2: [
          { field_1: 'A', field_2: false, count: 2 },
          { field_1: 'B', field_2: false, count: 3 },
          { field_1: 'B', field_2: true, count: 7 },
        ],
      },
      collapsedGroups: [],
      registry: mockRegistry,
      fields: [category, completed],
      bufferStartIndex: 5,
    })

    expect(result).toEqual([
      {
        type: 'header',
        depth: 1,
        field: completed,
        groupValues: { field_1: 'B', field_2: true },
        count: 7,
        collapsed: false,
      },
      { type: 'row', row: rows[0] },
      { type: 'row', row: rows[1] },
    ])
  })

  it('uses serialized metadata values for emitted header groupValues', () => {
    const field = { id: 1, type: 'single_select' }
    const option = { id: 10, value: 'Todo', color: 'light-blue' }
    const registry = {
      get() {
        return {
          isEqual(field, a, b) {
            return (a?.id || a) === (b?.id || b)
          },
          getRowValueFromGroupValue(field, value) {
            return value ? { id: value } : null
          },
        }
      },
    }

    const result = buildInterleavedList({
      rows: [{ id: 1, field_1: option }],
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [{ field_1: 10, count: 1 }],
      },
      collapsedGroups: [],
      registry,
      fields: [field],
    })

    expect(result[0]).toMatchObject({
      type: 'header',
      groupValues: { field_1: 10 },
      count: 1,
    })
  })

  it('does not mark sibling select groups as collapsed when only one is collapsed', () => {
    // Mirrors single-select isEqual which expects row-form values: when the
    // collapsed-state side is left in metadata-form (raw option ID), naive
    // comparisons return true for every option (`null === null`).
    const field = { id: 1, type: 'single_select' }
    const designOpt = { id: 4122, value: 'Design', color: 'light-blue' }
    const devOpt = { id: 4123, value: 'Development', color: 'red' }
    const registry = {
      get() {
        return {
          isEqual(field, a, b) {
            const aId = a?.id ?? null
            const bId = b?.id ?? null
            return aId === bId
          },
          getRowValueFromGroupValue(field, value) {
            return value ? { id: value } : null
          },
        }
      },
    }

    const result = buildInterleavedList({
      rows: [
        { id: 4, field_1: devOpt },
        { id: 8, field_1: devOpt },
      ],
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 4122, count: 2 },
          { field_1: 4123, count: 2 },
        ],
      },
      collapsedGroups: [{ field_1: 4122 }],
      registry,
      fields: [field],
    })

    const collapsedHeaders = result.filter(
      (item) => item.type === 'header' && item.collapsed
    )
    const expandedHeaders = result.filter(
      (item) => item.type === 'header' && !item.collapsed
    )
    expect(collapsedHeaders.map((h) => h.groupValues.field_1)).toEqual([4122])
    expect(expandedHeaders.map((h) => h.groupValues.field_1)).toEqual([4123])
    expect(
      result.filter((item) => item.type === 'row').map((item) => item.row.id)
    ).toEqual([4, 8])
  })

  it('keeps a collapsed select group header visible when its rows are excluded', () => {
    const field = { id: 1, type: 'single_select' }
    const doneOption = { id: 20, value: 'Done', color: 'dark-blue' }
    const registry = {
      get() {
        return {
          isEqual(field, a, b) {
            return (a?.id || a) === (b?.id || b)
          },
          getRowValueFromGroupValue(field, value) {
            return value ? { id: value } : null
          },
        }
      },
    }

    const result = buildInterleavedList({
      rows: [{ id: 2, field_1: doneOption }],
      activeGroupBys: [{ field: 1, order: 'ASC' }],
      groupByMetadata: {
        field_1: [
          { field_1: 10, count: 1 },
          { field_1: 20, count: 1 },
        ],
      },
      collapsedGroups: [{ field_1: 10 }],
      registry,
      fields: [field],
    })

    expect(result).toEqual([
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 10 },
        count: 1,
        collapsed: true,
      },
      {
        type: 'header',
        depth: 0,
        field,
        groupValues: { field_1: 20 },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: { id: 2, field_1: doneOption } },
    ])
  })

  it('handles nested group-bys with depth', () => {
    const field1 = { id: 1, type: 'text' }
    const field2 = { id: 2, type: 'text' }
    const rows = [
      { id: 1, field_1: 'A', field_2: 'X' },
      { id: 2, field_1: 'A', field_2: 'Y' },
      { id: 3, field_1: 'B', field_2: 'X' },
    ]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [
        { field: 1, order: 'ASC' },
        { field: 2, order: 'ASC' },
      ],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
        field_2: [
          { field_1: 'A', field_2: 'X', count: 1 },
          { field_1: 'A', field_2: 'Y', count: 1 },
          { field_1: 'B', field_2: 'X', count: 1 },
        ],
      },
      collapsedGroups: [],
      registry: mockRegistry,
      fields: [field1, field2],
    })

    expect(result).toEqual([
      {
        type: 'header',
        depth: 0,
        field: field1,
        groupValues: { field_1: 'A' },
        count: 2,
        collapsed: false,
      },
      {
        type: 'header',
        depth: 1,
        field: field2,
        groupValues: { field_1: 'A', field_2: 'X' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[0] },
      {
        type: 'header',
        depth: 1,
        field: field2,
        groupValues: { field_1: 'A', field_2: 'Y' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[1] },
      {
        type: 'header',
        depth: 0,
        field: field1,
        groupValues: { field_1: 'B' },
        count: 1,
        collapsed: false,
      },
      {
        type: 'header',
        depth: 1,
        field: field2,
        groupValues: { field_1: 'B', field_2: 'X' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[2] },
    ])
  })

  it('collapsing a parent hides all children', () => {
    const field1 = { id: 1, type: 'text' }
    const field2 = { id: 2, type: 'text' }
    const rows = [{ id: 3, field_1: 'B', field_2: 'X' }]

    const result = buildInterleavedList({
      rows,
      activeGroupBys: [
        { field: 1, order: 'ASC' },
        { field: 2, order: 'ASC' },
      ],
      groupByMetadata: {
        field_1: [
          { field_1: 'A', count: 2 },
          { field_1: 'B', count: 1 },
        ],
        field_2: [
          { field_1: 'A', field_2: 'X', count: 1 },
          { field_1: 'A', field_2: 'Y', count: 1 },
          { field_1: 'B', field_2: 'X', count: 1 },
        ],
      },
      collapsedGroups: [{ field_1: 'A' }],
      registry: mockRegistry,
      fields: [field1, field2],
    })

    expect(result).toEqual([
      {
        type: 'header',
        depth: 0,
        field: field1,
        groupValues: { field_1: 'A' },
        count: 2,
        collapsed: true,
      },
      {
        type: 'header',
        depth: 0,
        field: field1,
        groupValues: { field_1: 'B' },
        count: 1,
        collapsed: false,
      },
      {
        type: 'header',
        depth: 1,
        field: field2,
        groupValues: { field_1: 'B', field_2: 'X' },
        count: 1,
        collapsed: false,
      },
      { type: 'row', row: rows[0] },
    ])
  })
})

describe('findDepth0GroupPosition', () => {
  it('counts nested group headers in previous depth-0 group heights', () => {
    const category = { id: 1, type: 'text' }
    const completed = { id: 2, type: 'boolean' }

    expect(
      findDepth0GroupPosition({
        groupValues: { field_1: 'Development' },
        groupByMetadata: {
          field_1: [
            { field_1: 'Design', count: 2 },
            { field_1: 'Development', count: 3 },
          ],
          field_2: [
            { field_1: 'Design', field_2: false, count: 1 },
            { field_1: 'Design', field_2: true, count: 1 },
            { field_1: 'Development', field_2: false, count: 3 },
          ],
        },
        collapsedGroups: [],
        fields: [category, completed],
        registry: mockRegistry,
      })
    ).toEqual({ y: 210, count: 3 })
  })

  it('counts collapsed nested groups as header-only height', () => {
    const category = { id: 1, type: 'text' }
    const completed = { id: 2, type: 'boolean' }

    expect(
      findDepth0GroupPosition({
        groupValues: { field_1: 'Development' },
        groupByMetadata: {
          field_1: [
            { field_1: 'Design', count: 2 },
            { field_1: 'Development', count: 3 },
          ],
          field_2: [
            { field_1: 'Design', field_2: false, count: 1 },
            { field_1: 'Design', field_2: true, count: 1 },
            { field_1: 'Development', field_2: false, count: 3 },
          ],
        },
        collapsedGroups: [{ field_1: 'Design', field_2: false }],
        fields: [category, completed],
        registry: mockRegistry,
      })
    ).toEqual({ y: 177, count: 3 })
  })
})

describe('buildHeightIndex', () => {
  const colorField = { id: 5, type: 'text' }
  const sizeField = { id: 8, type: 'text' }

  const flatTree = [
    { path: { field_5: 'A' }, depth: 0, row_count: 2 },
    { path: { field_5: 'B' }, depth: 0, row_count: 3 },
  ]
  const nestedTree = [
    { path: { field_5: 'A' }, depth: 0, row_count: 3, children_count: 2 },
    { path: { field_5: 'A', field_8: '10' }, depth: 1, row_count: 2 },
    { path: { field_5: 'A', field_8: '20' }, depth: 1, row_count: 1 },
    { path: { field_5: 'B' }, depth: 0, row_count: 2, children_count: 1 },
    { path: { field_5: 'B', field_8: '10' }, depth: 1, row_count: 2 },
  ]

  it('returns an empty index for empty inputs', () => {
    const index = buildHeightIndex({
      treeNodes: [],
      collapsedGroups: [],
      fields: [colorField],
      registry: mockRegistry,
    })
    expect(index.items).toEqual([])
    expect(index.totalHeight).toBe(0)
    expect(index.totalRowCount).toBe(0)
  })

  it('builds header + rows items for a single-level tree', () => {
    const index = buildHeightIndex({
      treeNodes: flatTree,
      collapsedGroups: [],
      fields: [colorField],
      registry: mockRegistry,
    })

    expect(
      index.items.map((i) => [i.type, i.path?.field_5, i.rowCount ?? i.count])
    ).toEqual([
      ['group-header', 'A', 2],
      ['rows', 'A', 2],
      ['group-header', 'B', 3],
      ['rows', 'B', 3],
    ])
    expect(index.totalRowCount).toBe(5)
    expect(index.totalHeight).toBe(
      2 * GROUP_HEADER_HEIGHT + 5 * GROUP_ROW_HEIGHT
    )
    // prefix sums: 0, 48, 48+66, 48+66+48, 48+66+48+99
    expect(Array.from(index.prefixSums)).toEqual([
      0,
      GROUP_HEADER_HEIGHT,
      GROUP_HEADER_HEIGHT + 2 * GROUP_ROW_HEIGHT,
      2 * GROUP_HEADER_HEIGHT + 2 * GROUP_ROW_HEIGHT,
      2 * GROUP_HEADER_HEIGHT + 5 * GROUP_ROW_HEIGHT,
    ])
  })

  it('omits row blocks and skips descendants for a collapsed parent', () => {
    const index = buildHeightIndex({
      treeNodes: nestedTree,
      collapsedGroups: [{ field_5: 'A' }],
      fields: [colorField, sizeField],
      registry: mockRegistry,
    })

    // A is collapsed: only its header, then B's full subtree.
    expect(index.items.map((i) => [i.type, i.depth, i.path.field_5])).toEqual([
      ['group-header', 0, 'A'],
      ['group-header', 0, 'B'],
      ['group-header', 1, 'B'],
      ['rows', 1, 'B'],
    ])
    // A's rows must not contribute to totalRowCount.
    expect(index.totalRowCount).toBe(2)
  })

  it('treats every group as collapsed in collapse-mode unless explicitly expanded', () => {
    const index = buildHeightIndex({
      treeNodes: flatTree,
      collapsedGroups: [{ field_5: 'B' }],
      collapsedGroupsMode: COLLAPSED_GROUPS_MODE_COLLAPSE,
      fields: [colorField],
      registry: mockRegistry,
    })

    expect(index.items.map((i) => [i.type, i.path.field_5])).toEqual([
      ['group-header', 'A'],
      ['group-header', 'B'],
      ['rows', 'B'],
    ])
    expect(index.totalRowCount).toBe(3)
  })

  it('tracks startRowIndex so the row offset can be derived for any item', () => {
    const index = buildHeightIndex({
      treeNodes: nestedTree,
      collapsedGroups: [],
      fields: [colorField, sizeField],
      registry: mockRegistry,
    })

    // A.10 rows item is the second 'rows' item; A's leaf rows are 0..2,
    // so A.20's rows start at 2 and B.10's rows at 5.
    const rowsItems = index.items.filter((i) => i.type === 'rows')
    expect(
      rowsItems.map((r) => [r.path.field_8, r.startRowIndex, r.count])
    ).toEqual([
      ['10', 0, 2],
      ['20', 2, 1],
      ['10', 3, 2],
    ])
    expect(index.totalRowCount).toBe(5)
  })
})

describe('resolveScrollTop', () => {
  const colorField = { id: 5, type: 'text' }
  const tree = [
    { path: { field_5: 'A' }, depth: 0, count: 4 },
    { path: { field_5: 'B' }, depth: 0, count: 2 },
  ]

  const buildIndex = (collapsed = []) =>
    buildHeightIndex({
      treeNodes: tree,
      collapsedGroups: collapsed,
      fields: [colorField],
      registry: mockRegistry,
    })

  it('returns null for an empty index', () => {
    expect(
      resolveScrollTop(
        buildHeightIndex({
          treeNodes: [],
          collapsedGroups: [],
          fields: [colorField],
          registry: mockRegistry,
        }),
        100
      )
    ).toBeNull()
  })

  it('lands on the first header at scrollTop 0', () => {
    const index = buildIndex()
    const result = resolveScrollTop(index, 0)
    expect(result.itemIndex).toBe(0)
    expect(result.item.type).toBe('group-header')
    expect(result.rowOffset).toBe(0)
  })

  it('clamps scrollTop above totalHeight to the last item', () => {
    const index = buildIndex()
    const result = resolveScrollTop(index, index.totalHeight + 1000)
    // Last item is the 'rows' block of B. rowOffset must point into it.
    expect(result.item.type).toBe('rows')
    expect(result.rowOffset).toBe(index.totalRowCount - 1)
  })

  it('translates pixel offset inside a rows item to the right rowOffset', () => {
    const index = buildIndex()
    // First 'rows' item starts at HEADER_HEIGHT and contains 4 rows.
    // ScrollTop = HEADER_HEIGHT + 2 * ROW_HEIGHT lands on row index 2.
    const scrollTop = GROUP_HEADER_HEIGHT + 2 * GROUP_ROW_HEIGHT
    const result = resolveScrollTop(index, scrollTop)
    expect(result.item.type).toBe('rows')
    expect(result.rowOffset).toBe(2)
  })

  it('skips collapsed group rows when computing offsets', () => {
    const index = buildIndex([{ field_5: 'A' }])
    // With A collapsed, items: [headerA, headerB, rowsB].
    // A's rows do not count: total visible rows = 2.
    expect(index.totalRowCount).toBe(2)
    // ScrollTop just past both headers lands on row 0 of B.
    const result = resolveScrollTop(index, 2 * GROUP_HEADER_HEIGHT)
    expect(result.item.type).toBe('rows')
    expect(result.rowOffset).toBe(0)
  })
})

describe('buildHeightIndex with partial trees', () => {
  const colorField = { id: 5, type: 'text' }
  const sizeField = { id: 8, type: 'text' }

  it('emits a subtree-skeleton placeholder for an expanded but unloaded group', () => {
    const index = buildHeightIndex({
      treeNodes: [
        {
          path: { field_5: 'A' },
          depth: 0,
          row_count: 50,
          children_count: 5,
        },
      ],
      collapsedGroups: [{ field_5: 'A' }],
      collapsedGroupsMode: COLLAPSED_GROUPS_MODE_COLLAPSE,
      fields: [colorField, sizeField],
      registry: mockRegistry,
      loadedSubtrees: new Set([]),
    })

    expect(index.items.map((i) => i.type)).toEqual([
      'group-header',
      'subtree-skeleton',
    ])
    // Reserved height = children_count × header height (5 × 48).
    expect(index.items[1].height).toBe(5 * GROUP_HEADER_HEIGHT)
    expect(index.items[1].loading).toBe(false)
  })

  it('marks the skeleton as loading when the path is in loadingSubtrees', () => {
    const index = buildHeightIndex({
      treeNodes: [
        {
          path: { field_5: 'A' },
          depth: 0,
          row_count: 50,
          children_count: 3,
        },
      ],
      collapsedGroups: [{ field_5: 'A' }],
      collapsedGroupsMode: COLLAPSED_GROUPS_MODE_COLLAPSE,
      fields: [colorField, sizeField],
      registry: mockRegistry,
      loadedSubtrees: new Set([]),
      loadingSubtrees: new Set(['"A"']),
    })

    const skeleton = index.items.find((i) => i.type === 'subtree-skeleton')
    expect(skeleton.loading).toBe(true)
  })

  it('walks descendants when the path is in loadedSubtrees', () => {
    const index = buildHeightIndex({
      treeNodes: [
        {
          path: { field_5: 'A' },
          depth: 0,
          row_count: 2,
          children_count: 1,
        },
        { path: { field_5: 'A', field_8: '10' }, depth: 1, row_count: 2 },
      ],
      collapsedGroups: [{ field_5: 'A' }, { field_5: 'A', field_8: '10' }],
      collapsedGroupsMode: COLLAPSED_GROUPS_MODE_COLLAPSE,
      fields: [colorField, sizeField],
      registry: mockRegistry,
      loadedSubtrees: new Set(['"A"']),
    })

    expect(index.items.map((i) => [i.type, i.depth])).toEqual([
      ['group-header', 0],
      ['group-header', 1],
      ['rows', 1],
    ])
  })

  it('does not emit a skeleton for legacy mode when loadedSubtrees is null', () => {
    // Legacy callers don't pass loadedSubtrees and rely on the tree being
    // fully loaded; expanded groups must walk descendants normally.
    const index = buildHeightIndex({
      treeNodes: [
        {
          path: { field_5: 'A' },
          depth: 0,
          row_count: 1,
          children_count: 1,
        },
        { path: { field_5: 'A', field_8: '10' }, depth: 1, row_count: 1 },
      ],
      collapsedGroups: [],
      fields: [colorField, sizeField],
      registry: mockRegistry,
      // no loadedSubtrees -> legacy "everything's loaded" behaviour
    })
    expect(index.items.some((i) => i.type === 'subtree-skeleton')).toBe(false)
  })
})

describe('rowOffsetToY', () => {
  const colorField = { id: 5, type: 'text' }

  it('returns 0 when row offset 0 falls at a depth-0 group boundary', () => {
    const index = buildHeightIndex({
      treeNodes: [
        { path: { field_5: 'A' }, depth: 0, count: 4 },
        { path: { field_5: 'B' }, depth: 0, count: 2 },
      ],
      collapsedGroups: [],
      fields: [colorField],
      registry: mockRegistry,
    })
    // Buffer starts at row 0 → it includes the leading 'A' header, so the
    // buffer's first DOM item sits at y=0 (the header), not y=48 (row 0).
    expect(rowOffsetToY(index, 0)).toBe(0)
  })

  it('returns the y of a mid-group row when no header is prepended', () => {
    const index = buildHeightIndex({
      treeNodes: [
        { path: { field_5: 'A' }, depth: 0, count: 4 },
        { path: { field_5: 'B' }, depth: 0, count: 2 },
      ],
      collapsedGroups: [],
      fields: [colorField],
      registry: mockRegistry,
    })
    // Row 2 is mid-group A; the buffer at index 2 has no leading header,
    // so we return the y of the row itself.
    expect(rowOffsetToY(index, 2)).toBe(
      GROUP_HEADER_HEIGHT + 2 * GROUP_ROW_HEIGHT
    )
  })

  it('returns the y of B header when buffer starts at the first row of B', () => {
    const index = buildHeightIndex({
      treeNodes: [
        { path: { field_5: 'A' }, depth: 0, count: 4 },
        { path: { field_5: 'B' }, depth: 0, count: 2 },
      ],
      collapsedGroups: [],
      fields: [colorField],
      registry: mockRegistry,
    })
    // Items: headerA(y=0), rowsA(y=48, count=4), headerB(y=180), rowsB(y=228).
    // Row 4 is the first row of group B; the buffer prepends B's header,
    // so the y must be the header's y (180), not the row's y (228).
    const expected = GROUP_HEADER_HEIGHT + 4 * GROUP_ROW_HEIGHT
    expect(rowOffsetToY(index, 4)).toBe(expected)
  })

  it('returns 0 when all groups are collapsed and no rows exist', () => {
    const index = buildHeightIndex({
      treeNodes: [
        { path: { field_5: 'A' }, depth: 0, count: 4 },
        { path: { field_5: 'B' }, depth: 0, count: 2 },
      ],
      collapsedGroups: [{ field_5: 'A' }, { field_5: 'B' }],
      fields: [colorField],
      registry: mockRegistry,
    })
    expect(index.totalRowCount).toBe(0)
    // bufferStartIndex is 0 and the first item is headerA at y=0.
    expect(rowOffsetToY(index, 0)).toBe(0)
  })
})
