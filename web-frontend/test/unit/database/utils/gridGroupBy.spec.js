import {
  getGroupByCollapseAllState,
  shouldUseGroupByDepthPages,
  projectGroupByCollapseState,
  makeSectionRowsMap,
  getDefinedRowsFromSectionRows,
  groupPathDefaults,
  canMoveRowsAcrossGroupByFields,
  hasWritableGroupByPathChange,
  groupPathFromRow,
  getGroupByPathDepth,
  getGroupByPathPrefix,
  groupByPathsMatchAtDepth,
  groupByPathsHaveSameParent,
  getGroupByNodeRowCount,
  getAfterGroupByNodeSubtreeIndex,
  findGroupByNodeInsertionIndex,
  reindexGroupByTreeSiblingMetadata,
  updateGroupByTreeNodesForPath,
  getOrderedGroupByDataPageNodes,
  updateGroupByDataPageForPath,
  updateGroupByDataPagesForPath,
  isGroupByDataPageLoaded,
  getMissingGroupBySectionRanges,
  placeAbsoluteRowsIntoSections,
  getGroupByAbsoluteRangesForVisibleRange,
  rowBelongsToGroupBySection,
  getGroupByRowInsertLocation,
  getGroupByParentRowOffset,
} from '@baserow/modules/database/utils/gridGroupBy'
import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'

const textField = (id) => ({ id, name: `field ${id}`, type: 'text' })

/**
 * A minimal field-type registry. For text fields the group value and the row value
 * are identical, so the identity transforms are a faithful stand-in. The default
 * `default` sort compares `field_<id>` string values ascending/descending.
 */
const makeRegistry = (overrides = {}) => ({
  get(_namespace, _type) {
    const defaultSortTypes = () => ({
      default: {
        function: (fieldName, order) => (a, b) => {
          const va = a[fieldName]
          const vb = b[fieldName]
          const cmp = va < vb ? -1 : va > vb ? 1 : 0
          return order === 'DESC' ? -cmp : cmp
        },
      },
    })
    const instance = {
      canWriteFieldValues: () => true,
      getRowValueFromGroupValue: (_field, groupValue) => groupValue,
      getGroupValueFromRowValue: (_field, rowValue) => rowValue,
      getSortTypes: defaultSortTypes,
      getGroupBySort(name, order, _field, sortType) {
        const types = this.getSortTypes()
        const resolved = types[sortType] || types.default
        return resolved.function(name, order)
      },
      ...overrides,
    }
    return instance
  },
})

describe('gridGroupBy collapse state', () => {
  test('getGroupByCollapseAllState produces an empty exception list per mode', () => {
    expect(getGroupByCollapseAllState(true)).toEqual({
      mode: 'collapse',
      paths: [],
    })
    expect(getGroupByCollapseAllState(false)).toEqual({
      mode: 'expand',
      paths: [],
    })
  })

  test('shouldUseGroupByDepthPages requires initialized collapse-all with empty exceptions', () => {
    expect(
      shouldUseGroupByDepthPages({
        collapseInitialized: true,
        collapse: { mode: 'collapse', paths: [] },
      })
    ).toBe(true)
    // Expanded pages per parent (descends to leaves), not by depth.
    expect(
      shouldUseGroupByDepthPages({
        collapseInitialized: true,
        collapse: { mode: 'expand', paths: [] },
      })
    ).toBe(false)
    // Not initialized.
    expect(
      shouldUseGroupByDepthPages({
        collapseInitialized: false,
        collapse: { mode: 'collapse', paths: [] },
      })
    ).toBe(false)
    // Has exceptions, so the cheap depth-page path is not safe.
    expect(
      shouldUseGroupByDepthPages({
        collapseInitialized: true,
        collapse: { mode: 'collapse', paths: [{ field_1: 'A' }] },
      })
    ).toBe(false)
    // Unknown mode.
    expect(
      shouldUseGroupByDepthPages({
        collapseInitialized: true,
        collapse: { mode: 'partial', paths: [] },
      })
    ).toBe(false)
  })

  describe('projectGroupByCollapseState', () => {
    test('falsy collapse resets to expand-all', () => {
      expect(
        projectGroupByCollapseState(null, [textField(1)], [textField(1)])
      ).toEqual({ mode: 'expand', paths: [] })
    })

    test('preserves paths when the leading field order is unchanged (level added)', () => {
      const previous = [textField(1)]
      const next = [textField(1), textField(2)]
      const collapse = {
        mode: 'collapse',
        paths: [{ field_1: 'A' }, { field_1: 'B' }],
      }
      expect(projectGroupByCollapseState(collapse, previous, next)).toEqual(
        collapse
      )
    })

    test('trims deeper path entries to the available group-by fields (level removed)', () => {
      const previous = [textField(1), textField(2)]
      const next = [textField(1)]
      const collapse = {
        mode: 'collapse',
        paths: [{ field_1: 'A', field_2: 'X' }],
      }
      expect(projectGroupByCollapseState(collapse, previous, next)).toEqual({
        mode: 'collapse',
        paths: [{ field_1: 'A' }],
      })
    })

    test('deduplicates paths that collapse to the same prefix after trimming', () => {
      const previous = [textField(1), textField(2)]
      const next = [textField(1)]
      const collapse = {
        mode: 'collapse',
        paths: [
          { field_1: 'A', field_2: 'X' },
          { field_1: 'A', field_2: 'Y' },
        ],
      }
      expect(projectGroupByCollapseState(collapse, previous, next)).toEqual({
        mode: 'collapse',
        paths: [{ field_1: 'A' }],
      })
    })

    test('resets to expand-all when the leading field order changes (reorder)', () => {
      const previous = [textField(1), textField(2)]
      const next = [textField(2), textField(1)]
      const collapse = {
        mode: 'collapse',
        paths: [{ field_1: 'A', field_2: 'X' }],
      }
      expect(projectGroupByCollapseState(collapse, previous, next)).toEqual({
        mode: 'expand',
        paths: [],
      })
    })

    test('with no previous fields, only keeps paths anchored on the new first field', () => {
      const collapse = {
        mode: 'collapse',
        paths: [{ field_1: 'A' }, { field_9: 'Z' }],
      }
      // The path that does not contain the new first field cannot be projected,
      // so the whole projection is abandoned and reset to expand-all.
      expect(projectGroupByCollapseState(collapse, [], [textField(1)])).toEqual(
        { mode: 'expand', paths: [] }
      )
    })

    test('with no previous fields and all paths anchored, projects to the first field prefix', () => {
      const collapse = {
        mode: 'collapse',
        paths: [{ field_1: 'A', field_2: 'X' }],
      }
      expect(
        projectGroupByCollapseState(collapse, [], [textField(1), textField(2)])
      ).toEqual({
        mode: 'collapse',
        paths: [{ field_1: 'A', field_2: 'X' }],
      })
    })
  })
})

describe('gridGroupBy path helpers', () => {
  test('getGroupByPathDepth counts only the contiguous leading fields present', () => {
    const fields = [textField(1), textField(2), textField(3)]
    expect(getGroupByPathDepth({}, fields)).toBe(0)
    expect(getGroupByPathDepth({ field_1: 'A' }, fields)).toBe(1)
    expect(getGroupByPathDepth({ field_1: 'A', field_2: 'B' }, fields)).toBe(2)
    // A gap in the chain stops the count at the gap.
    expect(getGroupByPathDepth({ field_1: 'A', field_3: 'C' }, fields)).toBe(1)
  })

  test('getGroupByPathPrefix returns the path up to and including the given depth', () => {
    const fields = [textField(1), textField(2), textField(3)]
    const path = { field_1: 'A', field_2: 'B', field_3: 'C' }
    expect(getGroupByPathPrefix(path, fields, 0)).toEqual({ field_1: 'A' })
    expect(getGroupByPathPrefix(path, fields, 1)).toEqual({
      field_1: 'A',
      field_2: 'B',
    })
  })

  test('getGroupByPathPrefix keeps null group values', () => {
    const fields = [textField(1), textField(2)]
    const path = { field_1: null, field_2: 'B' }
    expect(getGroupByPathPrefix(path, fields, 1)).toEqual({
      field_1: null,
      field_2: 'B',
    })
  })

  test('groupByPathsMatchAtDepth compares the prefix up to depth', () => {
    const fields = [textField(1), textField(2)]
    const left = { field_1: 'A', field_2: 'X' }
    const right = { field_1: 'A', field_2: 'Y' }
    // Same depth-0 prefix.
    expect(groupByPathsMatchAtDepth(left, right, fields, 0)).toBe(true)
    // Differ at depth 1.
    expect(groupByPathsMatchAtDepth(left, right, fields, 1)).toBe(false)
  })

  test('groupByPathsHaveSameParent ignores the leaf at depth and is always true at depth 0', () => {
    const fields = [textField(1), textField(2)]
    const left = { field_1: 'A', field_2: 'X' }
    const right = { field_1: 'A', field_2: 'Y' }
    const other = { field_1: 'B', field_2: 'X' }
    expect(groupByPathsHaveSameParent(left, right, fields, 0)).toBe(true)
    expect(groupByPathsHaveSameParent(left, other, fields, 0)).toBe(true)
    // Depth 1: parent is field_1, so A/X and A/Y share a parent but A and B do not.
    expect(groupByPathsHaveSameParent(left, right, fields, 1)).toBe(true)
    expect(groupByPathsHaveSameParent(left, other, fields, 1)).toBe(false)
  })

  test('groupPathFromRow maps each grouped field through the registry', () => {
    const fields = [textField(1), textField(2)]
    const registry = makeRegistry()
    const row = { id: 5, field_1: 'A', field_2: null, field_3: 'ignored' }
    expect(groupPathFromRow(row, fields, registry)).toEqual({
      field_1: 'A',
      field_2: null,
    })
  })

  test('groupPathDefaults only includes writable fields present in the path', () => {
    const fields = [textField(1), textField(2), textField(3)]
    const registry = makeRegistry({
      // field 2 is read-only and must be skipped.
      canWriteFieldValues: (field) => field.id !== 2,
    })
    const path = { field_1: 'A', field_2: 'B' }
    // field_3 is absent from the path; field_2 is not writable.
    expect(groupPathDefaults(path, fields, registry)).toEqual({ field_1: 'A' })
  })

  test('groupPathDefaults keeps null group values for writable fields', () => {
    const fields = [textField(1)]
    const registry = makeRegistry()
    expect(groupPathDefaults({ field_1: null }, fields, registry)).toEqual({
      field_1: null,
    })
  })

  test('groupPathDefaults prefers rich display values and falls back to the path', () => {
    const fields = [textField(1), textField(2)]
    const registry = makeRegistry({
      getRowValueFromGroupValue: (_field, groupValue) => ({ id: groupValue }),
    })
    const displayValue = { id: 10, value: 'Group A', color: 'blue' }

    expect(
      groupPathDefaults({ field_1: 10, field_2: 20 }, fields, registry, {
        field_1: displayValue,
      })
    ).toEqual({ field_1: displayValue, field_2: { id: 20 } })
  })

  test('cross-group moves require every grouped field to be writable', () => {
    const fields = [textField(1), textField(2)]
    expect(canMoveRowsAcrossGroupByFields(fields, makeRegistry())).toBe(true)
    expect(
      canMoveRowsAcrossGroupByFields(
        fields,
        makeRegistry({
          canWriteFieldValues: (field) => field.id !== 2,
        })
      )
    ).toBe(false)
  })

  test('selected-row placeholders depend only on the group fields that changed', () => {
    const fields = [textField(1), textField(2)]
    const registry = makeRegistry({
      canWriteFieldValues: (field) => field.id === 1,
    })
    const oldPath = { field_1: 'A', field_2: 'X' }

    expect(
      hasWritableGroupByPathChange(
        oldPath,
        { field_1: 'B', field_2: 'X' },
        fields,
        registry
      )
    ).toBe(true)
    expect(
      hasWritableGroupByPathChange(
        oldPath,
        { field_1: 'A', field_2: 'Y' },
        fields,
        registry
      )
    ).toBe(false)
  })
})

describe('gridGroupBy section rows', () => {
  test('makeSectionRowsMap converts sparse arrays to numeric-keyed maps and drops holes', () => {
    const rowA = { id: 1 }
    const rowB = { id: 2 }
    const sectionRows = {
      sectionA: { 0: rowA, 2: rowB },
    }
    const result = makeSectionRowsMap(sectionRows)
    const mapA = result.get('sectionA')
    expect(mapA.get(0)).toBe(rowA)
    expect(mapA.get(2)).toBe(rowB)
    expect(mapA.has(1)).toBe(false)
  })

  test('makeSectionRowsMap skips undefined entries', () => {
    const sectionRows = { s: { 0: undefined, 1: { id: 9 } } }
    const map = makeSectionRowsMap(sectionRows).get('s')
    expect(map.size).toBe(1)
    expect(map.get(1)).toEqual({ id: 9 })
  })

  test('getDefinedRowsFromSectionRows returns rows in ascending position order', () => {
    const sectionRows = {
      s: { 2: { id: 3 }, 0: { id: 1 }, 1: { id: 2 } },
    }
    expect(getDefinedRowsFromSectionRows(sectionRows, 's')).toEqual([
      { id: 1 },
      { id: 2 },
      { id: 3 },
    ])
  })

  test('getDefinedRowsFromSectionRows can exclude a row id', () => {
    const sectionRows = {
      s: { 0: { id: 1 }, 1: { id: 2 }, 2: { id: 3 } },
    }
    expect(getDefinedRowsFromSectionRows(sectionRows, 's', 2)).toEqual([
      { id: 1 },
      { id: 3 },
    ])
  })

  test('getDefinedRowsFromSectionRows returns empty list for an unknown section', () => {
    expect(getDefinedRowsFromSectionRows({}, 'missing')).toEqual([])
  })
})

describe('gridGroupBy node helpers', () => {
  test('getGroupByNodeRowCount reads row_count and defaults to 0', () => {
    expect(getGroupByNodeRowCount({ row_count: 4 })).toBe(4)
    expect(getGroupByNodeRowCount({ row_count: 0 })).toBe(0)
    expect(getGroupByNodeRowCount({})).toBe(0)
  })

  test('getAfterGroupByNodeSubtreeIndex skips over deeper descendants', () => {
    const nodes = [
      { path: { field_1: 'A' }, depth: 0 },
      { path: { field_1: 'A', field_2: 'X' }, depth: 1 },
      { path: { field_1: 'A', field_2: 'Y' }, depth: 1 },
      { path: { field_1: 'B' }, depth: 0 },
    ]
    // The subtree of node 0 (A) covers indices 1 and 2; next sibling is at 3.
    expect(getAfterGroupByNodeSubtreeIndex(nodes, 0)).toBe(3)
    // A leaf node's subtree is just itself.
    expect(getAfterGroupByNodeSubtreeIndex(nodes, 1)).toBe(2)
    // Last node returns nodes.length.
    expect(getAfterGroupByNodeSubtreeIndex(nodes, 3)).toBe(4)
  })

  describe('findGroupByNodeInsertionIndex', () => {
    const fields = [textField(1)]
    const groupBys = [{ field: 1, order: 'ASC', type: 'default' }]
    const registry = makeRegistry()

    test('inserts a new sibling before the first node that sorts after it', () => {
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 1 },
        { path: { field_1: 'C' }, depth: 0, row_count: 1 },
      ]
      const node = { path: { field_1: 'B' }, depth: 0 }
      expect(
        findGroupByNodeInsertionIndex(nodes, node, fields, groupBys, registry)
      ).toBe(1)
    })

    test('appends a node that sorts after all existing siblings', () => {
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 1 },
        { path: { field_1: 'B' }, depth: 0, row_count: 1 },
      ]
      const node = { path: { field_1: 'Z' }, depth: 0 }
      expect(
        findGroupByNodeInsertionIndex(nodes, node, fields, groupBys, registry)
      ).toBe(2)
    })

    test('inserts at the front when it sorts before all siblings', () => {
      const nodes = [
        { path: { field_1: 'B' }, depth: 0, row_count: 1 },
        { path: { field_1: 'C' }, depth: 0, row_count: 1 },
      ]
      const node = { path: { field_1: 'A' }, depth: 0 }
      expect(
        findGroupByNodeInsertionIndex(nodes, node, fields, groupBys, registry)
      ).toBe(0)
    })

    test('inserts a child after its parent subtree, scoped to the same parent', () => {
      const twoFields = [textField(1), textField(2)]
      const childGroupBys = [
        { field: 1, order: 'ASC', type: 'default' },
        { field: 2, order: 'ASC', type: 'default' },
      ]
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 2 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 1 },
        { path: { field_1: 'B' }, depth: 0, row_count: 1 },
        { path: { field_1: 'B', field_2: 'X' }, depth: 1, row_count: 1 },
      ]
      // New child A/Z belongs under parent A and sorts after A/X.
      const node = { path: { field_1: 'A', field_2: 'Z' }, depth: 1 }
      expect(
        findGroupByNodeInsertionIndex(
          nodes,
          node,
          twoFields,
          childGroupBys,
          registry
        )
      ).toBe(2)
    })
  })

  describe('reindexGroupByTreeSiblingMetadata', () => {
    test('recomputes sibling_index and row_offset for a flat list', () => {
      const fields = [textField(1)]
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 3 },
        { path: { field_1: 'B' }, depth: 0, row_count: 2 },
        { path: { field_1: 'C' }, depth: 0, row_count: 5 },
      ]
      const result = reindexGroupByTreeSiblingMetadata(nodes, fields)
      expect(
        result.map((n) => ({
          field: n.path.field_1,
          sibling_index: n.sibling_index,
          row_offset: n.row_offset,
        }))
      ).toEqual([
        { field: 'A', sibling_index: 0, row_offset: 0 },
        { field: 'B', sibling_index: 1, row_offset: 3 },
        { field: 'C', sibling_index: 2, row_offset: 5 },
      ])
    })

    test('does not mutate the input nodes', () => {
      const fields = [textField(1)]
      const nodes = [{ path: { field_1: 'A' }, depth: 0, row_count: 3 }]
      const result = reindexGroupByTreeSiblingMetadata(nodes, fields)
      expect(nodes[0]).not.toHaveProperty('sibling_index')
      expect(result[0]).not.toBe(nodes[0])
    })

    test('row_offset of children is anchored at the parent and reset per parent', () => {
      const fields = [textField(1), textField(2)]
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 3 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 2 },
        { path: { field_1: 'A', field_2: 'Y' }, depth: 1, row_count: 1 },
        { path: { field_1: 'B' }, depth: 0, row_count: 4 },
        { path: { field_1: 'B', field_2: 'X' }, depth: 1, row_count: 4 },
      ]
      const result = reindexGroupByTreeSiblingMetadata(nodes, fields)
      const byKey = Object.fromEntries(
        result.map((n) => [pathKey(n.path, fields), n])
      )
      // Top-level offsets accumulate across A then B.
      expect(byKey[pathKey({ field_1: 'A' }, fields)]).toMatchObject({
        sibling_index: 0,
        row_offset: 0,
      })
      expect(byKey[pathKey({ field_1: 'B' }, fields)]).toMatchObject({
        sibling_index: 1,
        row_offset: 3,
      })
      // A's children start at A's row_offset (0) and accumulate.
      expect(
        byKey[pathKey({ field_1: 'A', field_2: 'X' }, fields)]
      ).toMatchObject({ sibling_index: 0, row_offset: 0 })
      expect(
        byKey[pathKey({ field_1: 'A', field_2: 'Y' }, fields)]
      ).toMatchObject({ sibling_index: 1, row_offset: 2 })
      // B's child sibling_index resets to 0, offset anchored at B (3).
      expect(
        byKey[pathKey({ field_1: 'B', field_2: 'X' }, fields)]
      ).toMatchObject({ sibling_index: 0, row_offset: 3 })
    })
  })

  describe('updateGroupByTreeNodesForPath', () => {
    const fields = [textField(1)]
    const groupBys = [{ field: 1, order: 'ASC', type: 'default' }]
    const registry = makeRegistry()

    test('increments the row_count of an existing node', () => {
      const nodes = [{ path: { field_1: 'A' }, depth: 0, row_count: 2 }]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'A' },
        fields,
        1,
        groupBys,
        registry
      )
      expect(result).toEqual([
        { path: { field_1: 'A' }, depth: 0, row_count: 3 },
      ])
    })

    test('preserves the confirmed aggregation row count on an optimistic count update', () => {
      const nodes = [
        {
          path: { field_1: 'A' },
          depth: 0,
          row_count: 2,
          aggregations: { field_2: 1 },
        },
      ]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'A' },
        fields,
        1,
        groupBys,
        registry
      )
      expect(result).toEqual([
        {
          path: { field_1: 'A' },
          depth: 0,
          row_count: 3,
          aggregations: { field_2: 1 },
          aggregation_row_count: 2,
        },
      ])
    })

    test('inserts a new node in sorted order on a positive delta', () => {
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 1 },
        { path: { field_1: 'C' }, depth: 0, row_count: 1 },
      ]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'B' },
        fields,
        1,
        groupBys,
        registry
      )
      expect(result.map((n) => n.path.field_1)).toEqual(['A', 'B', 'C'])
      expect(result[1]).toEqual({
        path: { field_1: 'B' },
        depth: 0,
        row_count: 1,
      })
    })

    test('does not create a node when the path is missing and delta is non-positive', () => {
      const nodes = [{ path: { field_1: 'A' }, depth: 0, row_count: 1 }]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'B' },
        fields,
        -1,
        groupBys,
        registry
      )
      expect(result.map((n) => n.path.field_1)).toEqual(['A'])
    })

    test('keeps an optimistically-emptied group at row_count 0 instead of pruning it', () => {
      const nodes = [{ path: { field_1: 'A' }, depth: 0, row_count: 1 }]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'A' },
        fields,
        -1,
        groupBys,
        registry
      )
      expect(result).toEqual([
        { path: { field_1: 'A' }, depth: 0, row_count: 0 },
      ])
    })

    test('clamps row_count at zero on an over-decrement', () => {
      const nodes = [{ path: { field_1: 'A' }, depth: 0, row_count: 1 }]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'A' },
        fields,
        -5,
        groupBys,
        registry
      )
      expect(result[0].row_count).toBe(0)
    })

    test('updates every level of a multi-level path', () => {
      const twoFields = [textField(1), textField(2)]
      const childGroupBys = [
        { field: 1, order: 'ASC', type: 'default' },
        { field: 2, order: 'ASC', type: 'default' },
      ]
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 1 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 1 },
      ]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'A', field_2: 'X' },
        twoFields,
        1,
        childGroupBys,
        registry
      )
      const byKey = Object.fromEntries(
        result.map((n) => [pathKey(n.path, twoFields), n])
      )
      expect(byKey[pathKey({ field_1: 'A' }, twoFields)].row_count).toBe(2)
      expect(
        byKey[pathKey({ field_1: 'A', field_2: 'X' }, twoFields)].row_count
      ).toBe(2)
    })

    test('reindexes sibling metadata when nodes already carry it', () => {
      const nodes = [
        {
          path: { field_1: 'A' },
          depth: 0,
          row_count: 1,
          sibling_index: 0,
          row_offset: 0,
        },
        {
          path: { field_1: 'C' },
          depth: 0,
          row_count: 1,
          sibling_index: 1,
          row_offset: 1,
        },
      ]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'B' },
        fields,
        1,
        groupBys,
        registry
      )
      expect(
        result.map((n) => ({
          field: n.path.field_1,
          sibling_index: n.sibling_index,
          row_offset: n.row_offset,
        }))
      ).toEqual([
        { field: 'A', sibling_index: 0, row_offset: 0 },
        { field: 'B', sibling_index: 1, row_offset: 1 },
        { field: 'C', sibling_index: 2, row_offset: 2 },
      ])
    })

    test('forceSiblingMetadata reindexes even when none is present', () => {
      const nodes = [
        { path: { field_1: 'A' }, depth: 0, row_count: 2 },
        { path: { field_1: 'B' }, depth: 0, row_count: 3 },
      ]
      const result = updateGroupByTreeNodesForPath(
        nodes,
        { field_1: 'A' },
        fields,
        1,
        groupBys,
        registry,
        true
      )
      expect(result.map((n) => n.row_offset)).toEqual([0, 3])
      expect(result.map((n) => n.sibling_index)).toEqual([0, 1])
    })
  })
})

describe('gridGroupBy paged tree maintenance', () => {
  const fields = [textField(1)]
  const groupBys = [{ field: 1, order: 'ASC', type: 'default' }]
  const registry = makeRegistry()

  test('getOrderedGroupByDataPageNodes orders by sibling_index falling back to key', () => {
    const nodes = {
      5: { path: { field_1: 'C' }, sibling_index: 2 },
      3: { path: { field_1: 'A' }, sibling_index: 0 },
      4: { path: { field_1: 'B' }, sibling_index: 1 },
    }
    expect(
      getOrderedGroupByDataPageNodes(nodes).map(({ node }) => node.path.field_1)
    ).toEqual(['A', 'B', 'C'])
  })

  test('getOrderedGroupByDataPageNodes falls back to the numeric key when sibling_index is absent', () => {
    const nodes = {
      2: { path: { field_1: 'C' } },
      0: { path: { field_1: 'A' } },
      1: { path: { field_1: 'B' } },
    }
    expect(
      getOrderedGroupByDataPageNodes(nodes).map(({ index }) => index)
    ).toEqual([0, 1, 2])
  })

  test('getOrderedGroupByDataPageNodes tolerates null/undefined', () => {
    expect(getOrderedGroupByDataPageNodes(null)).toEqual([])
    expect(getOrderedGroupByDataPageNodes(undefined)).toEqual([])
  })

  describe('updateGroupByDataPageForPath', () => {
    test('increments the row_count of a matching node and keeps offsets normalized', () => {
      const page = {
        nodes: {
          0: {
            path: { field_1: 'A' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
          },
          1: {
            path: { field_1: 'B' },
            depth: 0,
            row_count: 3,
            sibling_index: 1,
            row_offset: 2,
          },
        },
        totalSiblingCount: 2,
        rowOffset: 0,
      }
      const result = updateGroupByDataPageForPath({
        page,
        path: { field_1: 'A' },
        fields,
        depth: 0,
        delta: 1,
        groupBys,
        registry,
      })
      expect(result.nodes[0].row_count).toBe(3)
      // B's offset shifts because A now has one more row.
      expect(result.nodes[1].row_offset).toBe(3)
      expect(result.totalSiblingCount).toBe(2)
    })

    test('preserves the confirmed aggregation row count on a paged optimistic count update', () => {
      const page = {
        nodes: {
          0: {
            path: { field_1: 'A' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
            aggregations: { field_2: 1 },
          },
        },
        totalSiblingCount: 1,
        rowOffset: 0,
      }
      const result = updateGroupByDataPageForPath({
        page,
        path: { field_1: 'A' },
        fields,
        depth: 0,
        delta: 1,
        groupBys,
        registry,
      })
      expect(result.nodes[0]).toEqual({
        path: { field_1: 'A' },
        depth: 0,
        row_count: 3,
        sibling_index: 0,
        row_offset: 0,
        aggregations: { field_2: 1 },
        aggregation_row_count: 2,
      })
    })

    test('increments a matching node without densifying sparse loaded windows', () => {
      const page = {
        nodes: {
          0: {
            path: { field_1: 'A' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
          },
          40: {
            path: { field_1: 'M' },
            depth: 0,
            row_count: 3,
            sibling_index: 40,
            row_offset: 200,
          },
          80: {
            path: { field_1: 'Z' },
            depth: 0,
            row_count: 4,
            sibling_index: 80,
            row_offset: 400,
          },
        },
        totalSiblingCount: 120,
        rowOffset: 0,
      }
      const result = updateGroupByDataPageForPath({
        page,
        path: { field_1: 'M' },
        fields,
        depth: 0,
        delta: 1,
        groupBys,
        registry,
      })
      expect(Object.keys(result.nodes).map(Number)).toEqual([0, 40, 80])
      expect(result.nodes[40].row_count).toBe(4)
      expect(result.nodes[40].row_offset).toBe(200)
      expect(result.nodes[80].row_offset).toBe(401)
      expect(result.totalSiblingCount).toBe(120)
    })

    test('keeps an optimistically-emptied node at row_count 0', () => {
      const page = {
        nodes: {
          0: {
            path: { field_1: 'A' },
            depth: 0,
            row_count: 1,
            sibling_index: 0,
            row_offset: 0,
          },
        },
        totalSiblingCount: 1,
        rowOffset: 0,
      }
      const result = updateGroupByDataPageForPath({
        page,
        path: { field_1: 'A' },
        fields,
        depth: 0,
        delta: -1,
        groupBys,
        registry,
      })
      expect(result.nodes[0].row_count).toBe(0)
      expect(result.totalSiblingCount).toBe(1)
    })

    test('inserts a new node for a positive delta and grows totalSiblingCount', () => {
      const page = {
        nodes: {
          0: {
            path: { field_1: 'A' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
          },
        },
        totalSiblingCount: 1,
        rowOffset: 0,
      }
      const result = updateGroupByDataPageForPath({
        page,
        path: { field_1: 'B' },
        fields,
        depth: 0,
        delta: 1,
        groupBys,
        registry,
      })
      expect(result.totalSiblingCount).toBe(2)
      const paths = Object.values(result.nodes).map((n) => n.path.field_1)
      expect(paths).toContain('B')
    })

    test('inserts a new node without densifying sparse loaded windows', () => {
      const page = {
        nodes: {
          0: {
            path: { field_1: 'A' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
          },
          40: {
            path: { field_1: 'M' },
            depth: 0,
            row_count: 3,
            sibling_index: 40,
            row_offset: 200,
          },
          80: {
            path: { field_1: 'Z' },
            depth: 0,
            row_count: 4,
            sibling_index: 80,
            row_offset: 400,
          },
        },
        totalSiblingCount: 120,
        rowOffset: 0,
      }
      const result = updateGroupByDataPageForPath({
        page,
        path: { field_1: 'F' },
        fields,
        depth: 0,
        delta: 1,
        groupBys,
        registry,
      })
      // The new group slots in at M's sibling index; M and Z keep their real (sparse)
      // keys shifted by one rather than being compacted to 0..2.
      expect(
        Object.keys(result.nodes)
          .map(Number)
          .sort((a, b) => a - b)
      ).toEqual([0, 40, 41, 81])
      expect(result.nodes[0].path.field_1).toBe('A')
      expect(result.nodes[40].path.field_1).toBe('F')
      expect(result.nodes[41].path.field_1).toBe('M')
      expect(result.nodes[81].path.field_1).toBe('Z')
      expect(result.nodes[40].row_offset).toBe(200)
      expect(result.nodes[41].row_offset).toBe(201)
      expect(result.nodes[81].row_offset).toBe(401)
      expect(result.totalSiblingCount).toBe(121)
    })

    test('returns the page unchanged when inserting a missing node with non-positive delta', () => {
      const page = {
        nodes: {
          0: {
            path: { field_1: 'A' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
          },
        },
        totalSiblingCount: 1,
        rowOffset: 0,
      }
      const result = updateGroupByDataPageForPath({
        page,
        path: { field_1: 'B' },
        fields,
        depth: 0,
        delta: -1,
        groupBys,
        registry,
      })
      expect(result).toBe(page)
    })
  })

  describe('updateGroupByDataPagesForPath', () => {
    test('updates the top-level page for a depth-1 path', () => {
      const pages = {
        [pathKey({}, fields)]: {
          parentPath: {},
          nodes: {
            0: {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 2,
              sibling_index: 0,
              row_offset: 0,
            },
          },
          totalSiblingCount: 1,
          rowOffset: 0,
        },
      }
      const result = updateGroupByDataPagesForPath(
        pages,
        { field_1: 'A' },
        fields,
        1,
        groupBys,
        registry
      )
      expect(result[pathKey({}, fields)].nodes[0].row_count).toBe(3)
    })

    test('creates a missing child page on a positive delta for a multi-level path', () => {
      const twoFields = [textField(1), textField(2)]
      const childGroupBys = [
        { field: 1, order: 'ASC', type: 'default' },
        { field: 2, order: 'ASC', type: 'default' },
      ]
      const topKey = pathKey({}, twoFields)
      const childKey = pathKey({ field_1: 'A' }, twoFields)
      const pages = {
        [topKey]: {
          parentPath: {},
          nodes: {
            0: {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 0,
              sibling_index: 0,
              row_offset: 0,
            },
          },
          totalSiblingCount: 1,
          rowOffset: 0,
        },
      }
      const result = updateGroupByDataPagesForPath(
        pages,
        { field_1: 'A', field_2: 'X' },
        twoFields,
        1,
        childGroupBys,
        registry
      )
      // The top-level A node is bumped to 1.
      expect(result[topKey].nodes[0].row_count).toBe(1)
      // A new child page keyed by the A prefix is created with the A/X node.
      expect(result[childKey]).toBeDefined()
      const childNodes = Object.values(result[childKey].nodes)
      expect(childNodes).toHaveLength(1)
      expect(childNodes[0]).toMatchObject({
        path: { field_1: 'A', field_2: 'X' },
        row_count: 1,
      })
    })

    test('skips a missing page when the delta is non-positive', () => {
      const result = updateGroupByDataPagesForPath(
        {},
        { field_1: 'A' },
        fields,
        -1,
        groupBys,
        registry
      )
      expect(result).toEqual({})
    })
  })

  describe('isGroupByDataPageLoaded', () => {
    const pages = {
      [pathKey({}, fields)]: {
        totalSiblingCount: 5,
        nodes: {
          0: { path: { field_1: 'A' } },
          1: { path: { field_1: 'B' } },
        },
      },
    }

    test('returns true when the requested slice is fully present', () => {
      expect(isGroupByDataPageLoaded(pages, {}, 0, 2, fields)).toBe(true)
    })

    test('returns false when part of the requested slice is missing', () => {
      expect(isGroupByDataPageLoaded(pages, {}, 0, 3, fields)).toBe(false)
    })

    test('returns true when the offset is at or beyond the total count', () => {
      expect(isGroupByDataPageLoaded(pages, {}, 5, 10, fields)).toBe(true)
    })

    test('returns false for an unknown page', () => {
      expect(
        isGroupByDataPageLoaded(pages, { field_1: 'Z' }, 0, 1, fields)
      ).toBe(false)
    })
  })
})

describe('gridGroupBy windowing helpers', () => {
  const fields = [textField(1)]
  const registry = makeRegistry()

  const section = (sectionKey, overrides = {}) => ({
    sectionKey,
    path: { field_1: sectionKey },
    sectionPath: { field_1: sectionKey },
    startPosition: 0,
    endPosition: 3,
    absoluteRowOffset: 0,
    ...overrides,
  })

  test('getMissingGroupBySectionRanges returns one range covering an empty section', () => {
    const ranges = getMissingGroupBySectionRanges({}, [section('A')])
    expect(ranges).toEqual([
      expect.objectContaining({
        sectionKey: 'A',
        startPosition: 0,
        endPosition: 3,
      }),
    ])
  })

  test('getMissingGroupBySectionRanges splits around already-loaded rows', () => {
    const sectionRows = { A: { 1: { id: 1 } } }
    const ranges = getMissingGroupBySectionRanges(sectionRows, [section('A')])
    expect(
      ranges.map(({ startPosition, endPosition }) => ({
        startPosition,
        endPosition,
      }))
    ).toEqual([
      { startPosition: 0, endPosition: 1 },
      { startPosition: 2, endPosition: 3 },
    ])
  })

  test('getMissingGroupBySectionRanges treats matching absoluteRows as present', () => {
    // The absolute row at offset 1 belongs to section A, so position 1 is filled.
    const absoluteRows = { 1: { id: 9, field_1: 'A' } }
    const ranges = getMissingGroupBySectionRanges(
      {},
      [section('A')],
      absoluteRows,
      fields,
      registry
    )
    expect(
      ranges.map(({ startPosition, endPosition }) => ({
        startPosition,
        endPosition,
      }))
    ).toEqual([
      { startPosition: 0, endPosition: 1 },
      { startPosition: 2, endPosition: 3 },
    ])
  })

  test('getMissingGroupBySectionRanges ignores an absoluteRow from a different section', () => {
    // The absolute row belongs to section B, so it does not fill section A.
    const absoluteRows = { 1: { id: 9, field_1: 'B' } }
    const ranges = getMissingGroupBySectionRanges(
      {},
      [section('A')],
      absoluteRows,
      fields,
      registry
    )
    expect(ranges).toEqual([
      expect.objectContaining({ startPosition: 0, endPosition: 3 }),
    ])
  })

  test('placeAbsoluteRowsIntoSections groups contiguous rows into placements', () => {
    const absoluteRows = {
      0: { id: 1, field_1: 'A' },
      1: { id: 2, field_1: 'A' },
    }
    const placements = placeAbsoluteRowsIntoSections({
      absoluteRows,
      sections: [section('A')],
      fields,
      registry,
    })
    expect(placements).toEqual([
      {
        sectionKey: 'A',
        startPosition: 0,
        rows: [
          { id: 1, field_1: 'A' },
          { id: 2, field_1: 'A' },
        ],
      },
    ])
  })

  test('placeAbsoluteRowsIntoSections breaks placements around gaps', () => {
    const absoluteRows = {
      0: { id: 1, field_1: 'A' },
      2: { id: 3, field_1: 'A' },
    }
    const placements = placeAbsoluteRowsIntoSections({
      absoluteRows,
      sections: [section('A')],
      fields,
      registry,
    })
    expect(placements).toEqual([
      { sectionKey: 'A', startPosition: 0, rows: [{ id: 1, field_1: 'A' }] },
      { sectionKey: 'A', startPosition: 2, rows: [{ id: 3, field_1: 'A' }] },
    ])
  })

  test('placeAbsoluteRowsIntoSections drops rows that do not belong to the section', () => {
    const absoluteRows = {
      0: { id: 1, field_1: 'A' },
      1: { id: 2, field_1: 'B' },
    }
    const placements = placeAbsoluteRowsIntoSections({
      absoluteRows,
      sections: [section('A')],
      fields,
      registry,
    })
    expect(placements).toEqual([
      { sectionKey: 'A', startPosition: 0, rows: [{ id: 1, field_1: 'A' }] },
    ])
  })

  test('placeAbsoluteRowsIntoSections skips positions reported as already loaded', () => {
    const absoluteRows = {
      0: { id: 1, field_1: 'A' },
      1: { id: 2, field_1: 'A' },
      2: { id: 3, field_1: 'A' },
    }
    // Position 1 is already materialized in the section (e.g. by an optimistic move),
    // so re-placing the stale absolute-offset cache there would duplicate/revert it.
    const placements = placeAbsoluteRowsIntoSections({
      absoluteRows,
      sections: [section('A')],
      fields,
      registry,
      isPositionLoaded: (sectionKey, position) =>
        sectionKey === 'A' && position === 1,
    })
    expect(placements).toEqual([
      { sectionKey: 'A', startPosition: 0, rows: [{ id: 1, field_1: 'A' }] },
      { sectionKey: 'A', startPosition: 2, rows: [{ id: 3, field_1: 'A' }] },
    ])
  })

  test('getGroupByAbsoluteRangesForVisibleRange maps a visible window to per-section requests', () => {
    const layout = {
      items: [
        {
          type: 'rowSection',
          firstGlobalRowOffset: 0,
          rowCount: 5,
          absoluteRowOffset: 100,
        },
        {
          type: 'rowSection',
          firstGlobalRowOffset: 5,
          rowCount: 5,
          absoluteRowOffset: 200,
        },
        // Non-row items are ignored.
        { type: 'header' },
      ],
    }
    // Visible range [3, 7) overlaps the tail of section 1 and the head of section 2.
    const ranges = getGroupByAbsoluteRangesForVisibleRange(layout, 3, 4)
    expect(ranges).toEqual([
      { offset: 103, limit: 2 },
      { offset: 200, limit: 2 },
    ])
  })

  test('getGroupByAbsoluteRangesForVisibleRange returns nothing when no section overlaps', () => {
    const layout = {
      items: [
        {
          type: 'rowSection',
          firstGlobalRowOffset: 0,
          rowCount: 2,
          absoluteRowOffset: 0,
        },
      ],
    }
    expect(getGroupByAbsoluteRangesForVisibleRange(layout, 10, 5)).toEqual([])
  })
})

describe('gridGroupBy row<->section mapping', () => {
  const fields = [textField(1)]
  const registry = makeRegistry()

  test('rowBelongsToGroupBySection matches a row to its section by group path', () => {
    const section = { sectionPath: { field_1: 'A' } }
    expect(
      rowBelongsToGroupBySection(
        { id: 1, field_1: 'A' },
        section,
        fields,
        registry
      )
    ).toBe(true)
    expect(
      rowBelongsToGroupBySection(
        { id: 2, field_1: 'B' },
        section,
        fields,
        registry
      )
    ).toBe(false)
  })

  test('rowBelongsToGroupBySection falls back to section.path', () => {
    const section = { path: { field_1: 'A' } }
    expect(
      rowBelongsToGroupBySection(
        { id: 1, field_1: 'A' },
        section,
        fields,
        registry
      )
    ).toBe(true)
  })

  test('rowBelongsToGroupBySection returns true when inputs are missing or the section is pathless', () => {
    expect(rowBelongsToGroupBySection(null, {}, fields, registry)).toBe(true)
    expect(rowBelongsToGroupBySection({ id: 1 }, {}, null, registry)).toBe(true)
    // A section without a path means "everything belongs".
    expect(
      rowBelongsToGroupBySection({ id: 1, field_1: 'A' }, {}, fields, registry)
    ).toBe(true)
  })

  test('rowBelongsToGroupBySection matches on a null group value', () => {
    const section = { sectionPath: { field_1: null } }
    expect(
      rowBelongsToGroupBySection(
        { id: 1, field_1: null },
        section,
        fields,
        registry
      )
    ).toBe(true)
    expect(
      rowBelongsToGroupBySection(
        { id: 2, field_1: 'A' },
        section,
        fields,
        registry
      )
    ).toBe(false)
  })

  test('rowBelongsToGroupBySection matches an m2m row regardless of id order', () => {
    // Root-cause regression: an optimistically-edited row whose m2m value lists the ids
    // in a different order than the section's server path must still belong to it.
    const section = { sectionPath: { field_1: [100, 200] } }
    expect(
      rowBelongsToGroupBySection(
        { id: 1, field_1: [200, 100] },
        section,
        fields,
        registry
      )
    ).toBe(true)
    // A genuinely different set still does not belong.
    expect(
      rowBelongsToGroupBySection(
        { id: 2, field_1: [100, 300] },
        section,
        fields,
        registry
      )
    ).toBe(false)
  })

  test('getGroupByRowInsertLocation derives path, section key, and sorted position', () => {
    const groupByFields = [textField(1)]
    // Group by field_1 but sort by a distinct field_2, so the new row has a single
    // unambiguous insert position (the previous setup grouped and sorted on the same
    // field with tied values, making the position non-deterministic).
    const allFields = [textField(1), textField(2)]
    const view = { sortings: [{ field: 2, order: 'ASC', type: 'default' }] }
    const layout = {
      items: [
        {
          type: 'rowSection',
          path: { field_1: 'G' },
        },
      ],
    }
    const sectionKey = pathKey({ field_1: 'G' }, groupByFields)
    const sectionRows = {
      [sectionKey]: {
        0: { id: 1, order: '1', field_1: 'G', field_2: 'A' },
        1: { id: 3, order: '3', field_1: 'G', field_2: 'C' },
      },
    }
    // The new row's field_2 'B' sorts between the section's 'A' and 'C' rows. Its `order`
    // ('5') is deliberately out of line with field_2 so a broken implementation that fell
    // back to the order tiebreak would place it last (position 2), not at position 1.
    const result = getGroupByRowInsertLocation({
      row: { id: 2, order: '5', field_1: 'G', field_2: 'B' },
      view,
      fields: allFields,
      registry,
      groupByFields,
      layout,
      sectionRows,
    })
    expect(result.path).toEqual({ field_1: 'G' })
    expect(result.sectionKey).toBe(sectionKey)
    expect(result.position).toBe(1)
  })

  test('getGroupByRowInsertLocation returns an absolute position for a windowed section', () => {
    const groupByFields = [textField(1)]
    const allFields = [textField(1), textField(2)]
    const view = { sortings: [{ field: 2, order: 'ASC', type: 'default' }] }
    const layout = {
      items: [
        {
          type: 'rowSection',
          path: { field_1: 'G' },
        },
      ],
    }
    const sectionKey = pathKey({ field_1: 'G' }, groupByFields)
    // The section's loaded window starts deep into the group (absolute positions
    // 100 and 101), as happens after scrolling into a large group. The insert
    // position must be expressed in that absolute space, not as a compacted index
    // into the two loaded rows.
    const sectionRows = {
      [sectionKey]: {
        100: { id: 1, order: '1', field_1: 'G', field_2: 'A' },
        101: { id: 3, order: '3', field_1: 'G', field_2: 'C' },
      },
    }
    const result = getGroupByRowInsertLocation({
      row: { id: 2, order: '5', field_1: 'G', field_2: 'B' },
      view,
      fields: allFields,
      registry,
      groupByFields,
      layout,
      sectionRows,
    })
    expect(result.path).toEqual({ field_1: 'G' })
    expect(result.sectionKey).toBe(sectionKey)
    // 'B' sorts between the rows at absolute positions 100 ('A') and 101 ('C'), so it
    // must be inserted at absolute position 101 (before the 'C' row), not at the
    // compacted index 1.
    expect(result.position).toBe(101)
  })
})

describe('getGroupByParentRowOffset', () => {
  const fields = [{ id: 2 }, { id: 3 }]
  const pages = {
    [pathKey({}, fields)]: {
      parentPath: {},
      nodes: {
        0: { path: { field_2: 'A' }, depth: 0, row_count: 2, row_offset: 0 },
        1: { path: { field_2: 'B' }, depth: 0, row_count: 3, row_offset: 2 },
      },
      totalSiblingCount: 2,
    },
    [pathKey({ field_2: 'B' }, fields)]: {
      parentPath: { field_2: 'B' },
      nodes: {
        0: {
          path: { field_2: 'B', field_3: 'X' },
          depth: 1,
          row_count: 3,
          row_offset: 2,
        },
      },
      totalSiblingCount: 1,
    },
  }

  test('returns 0 for the top-level parent', () => {
    expect(getGroupByParentRowOffset(pages, {}, fields)).toBe(0)
  })

  test('returns the row_offset of a loaded depth-0 parent group', () => {
    expect(getGroupByParentRowOffset(pages, { field_2: 'B' }, fields)).toBe(2)
  })

  test('returns the row_offset of a loaded depth-1 parent group', () => {
    expect(
      getGroupByParentRowOffset(pages, { field_2: 'B', field_3: 'X' }, fields)
    ).toBe(2)
  })

  test('returns undefined when the parent group is not loaded', () => {
    expect(getGroupByParentRowOffset(pages, { field_2: 'Z' }, fields)).toBe(
      undefined
    )
  })

  test('returns undefined when the parent page is missing', () => {
    expect(getGroupByParentRowOffset({}, { field_2: 'B' }, fields)).toBe(
      undefined
    )
  })
})
