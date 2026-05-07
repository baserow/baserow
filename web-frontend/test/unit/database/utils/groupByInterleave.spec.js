import { describe, expect, it } from 'vitest'

import {
  buildInterleavedList,
  COLLAPSED_GROUPS_MODE_COLLAPSE,
  findDepth0GroupPosition,
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
