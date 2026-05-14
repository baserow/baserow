/**
 * Tests for the pure render core of the grouped grid view. Each function
 * under test is a deterministic function of its inputs — no Vuex, no DOM,
 * no async. The whole point of the new architecture is that everything
 * the user *sees* is derived from these functions, so testing them
 * thoroughly catches visual regressions in milliseconds.
 */
import {
  HEADER_HEIGHT,
  ROW_HEIGHT,
  GROUP_GAP,
  buildLayout,
  pathKey,
  isPathCollapsed,
  getEffectiveRow,
  renderViewport,
  pixelToRowOffset,
  pixelRangeToRowOffsetRange,
  visibleSectionsInViewport,
} from '@baserow/modules/database/utils/gridGroupedRender'

const textField = (id) => ({ id, name: `f${id}`, type: 'text' })

// Build a per-section bucket map keyed by sectionKey. Each section's
// bucket is a `Map<positionInSection, RowData>` mirroring the store's
// `sectionRows` shape.
const buildSectionRows = (entries, fields) => {
  const map = new Map()
  for (const { path, rows } of entries) {
    const key = pathKey(path, fields)
    const bucket = new Map()
    rows.forEach((row, position) => bucket.set(position, row))
    map.set(key, bucket)
  }
  return map
}

describe('gridGroupedRender / buildLayout', () => {
  test('empty tree → empty layout', () => {
    const layout = buildLayout({
      nodes: [],
      collapse: { mode: 'expand', paths: [] },
      fields: [textField(1)],
    })
    expect(layout.items).toEqual([])
    expect(layout.totalHeight).toBe(0)
    expect(layout.totalRowCount).toBe(0)
  })

  test('single-level group-by, one expanded group → header + rowSection + addRow', () => {
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
      collapse: { mode: 'expand', paths: [] },
      fields: [textField(1)],
    })
    expect(layout.items).toHaveLength(3)
    expect(layout.items.map((it) => it.type)).toEqual([
      'header',
      'rowSection',
      'addRow',
    ])
    expect(layout.items[1]).toMatchObject({
      rowCount: 3,
      y: HEADER_HEIGHT,
      height: 3 * ROW_HEIGHT,
      firstGlobalRowOffset: 0,
    })
    expect(layout.items[2]).toMatchObject({
      type: 'addRow',
      y: HEADER_HEIGHT + 3 * ROW_HEIGHT,
      height: ROW_HEIGHT,
    })
    expect(layout.totalHeight).toBe(HEADER_HEIGHT + 4 * ROW_HEIGHT)
    expect(layout.totalRowCount).toBe(3)
  })

  test('collapsed group emits header only — no rowSection, no row pixels', () => {
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 5 }],
      collapse: { mode: 'expand', paths: [{ field_1: 'A' }] },
      fields: [textField(1)],
    })
    expect(layout.items).toHaveLength(1)
    expect(layout.items[0]).toMatchObject({
      type: 'header',
      collapsed: true,
      y: 0,
      height: HEADER_HEIGHT,
    })
    expect(layout.totalHeight).toBe(HEADER_HEIGHT)
    expect(layout.totalRowCount).toBe(0)
  })

  test('collapse mode "collapse" inverts the meaning of the paths list', () => {
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 2 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 4 },
      ],
      collapse: { mode: 'collapse', paths: [{ field_1: 'B' }] },
      fields: [textField(1)],
    })
    const aHeader = layout.items.find(
      (it) => it.type === 'header' && it.path.field_1 === 'A'
    )
    const bHeader = layout.items.find(
      (it) => it.type === 'header' && it.path.field_1 === 'B'
    )
    expect(aHeader.collapsed).toBe(true)
    expect(bHeader.collapsed).toBe(false)
    const rowSections = layout.items.filter((it) => it.type === 'rowSection')
    expect(rowSections).toHaveLength(1)
    expect(rowSections[0].path.field_1).toBe('B')
    expect(rowSections[0].rowCount).toBe(4)
  })

  test('2-level group-by: depth-0 expanded, depth-1 leaves get rowSections', () => {
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 5 },
        { path: { field_1: 'A', field_2: true }, depth: 1, rowCount: 2 },
        { path: { field_1: 'A', field_2: false }, depth: 1, rowCount: 3 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields: [textField(1), textField(2)],
    })
    expect(layout.items.map((it) => it.type)).toEqual([
      'header',
      'header',
      'rowSection',
      'addRow',
      'header',
      'rowSection',
      'addRow',
    ])
    const rowSections = layout.items.filter((it) => it.type === 'rowSection')
    expect(rowSections.map((s) => s.rowCount)).toEqual([2, 3])
    expect(layout.totalRowCount).toBe(5)
  })

  test('2-level group-by: firstGlobalRowOffset is the cumulative leaf row count', () => {
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 5 },
        { path: { field_1: 'A', field_2: true }, depth: 1, rowCount: 2 },
        { path: { field_1: 'A', field_2: false }, depth: 1, rowCount: 3 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 4 },
        { path: { field_1: 'B', field_2: true }, depth: 1, rowCount: 4 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields: [textField(1), textField(2)],
    })
    const rowSections = layout.items.filter((it) => it.type === 'rowSection')
    expect(rowSections.map((s) => s.firstGlobalRowOffset)).toEqual([0, 2, 5])
  })

  test('2-level group-by: collapsing the parent hides all descendant headers + sections', () => {
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 5 },
        { path: { field_1: 'A', field_2: true }, depth: 1, rowCount: 2 },
        { path: { field_1: 'A', field_2: false }, depth: 1, rowCount: 3 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 1 },
        { path: { field_1: 'B', field_2: true }, depth: 1, rowCount: 1 },
      ],
      collapse: { mode: 'expand', paths: [{ field_1: 'A' }] },
      fields: [textField(1), textField(2)],
    })
    const aItems = layout.items.filter((it) => it.path.field_1 === 'A')
    expect(aItems).toHaveLength(1)
    expect(aItems[0].type).toBe('header')
    expect(aItems[0].collapsed).toBe(true)
    // B is expanded: depth-0 header + depth-1 header + rowSection +
    // addRow trailer.
    const bItems = layout.items.filter((it) => it.path.field_1 === 'B')
    expect(bItems).toHaveLength(4)
    expect(bItems.map((it) => it.type)).toEqual([
      'header',
      'header',
      'rowSection',
      'addRow',
    ])
  })

  test('renders banners stacked in tree order even when row counts differ', () => {
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 100 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 1 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields: [textField(1)],
    })
    const bHeader = layout.items.find(
      (it) => it.type === 'header' && it.path.field_1 === 'B'
    )
    // A's banner + 100 rows + 1 addRow trailer + GROUP_GAP.
    expect(bHeader.y).toBe(
      HEADER_HEIGHT + 100 * ROW_HEIGHT + ROW_HEIGHT + GROUP_GAP
    )
  })
})

describe('gridGroupedRender / pathKey + isPathCollapsed', () => {
  test('pathKey produces deterministic strings independent of key order', () => {
    const a = pathKey({ field_1: 'X', field_2: true }, [
      textField(1),
      textField(2),
    ])
    const b = pathKey({ field_2: true, field_1: 'X' }, [
      textField(1),
      textField(2),
    ])
    expect(a).toBe(b)
  })

  test('isPathCollapsed obeys mode + presence in the list', () => {
    const fields = [textField(1)]
    expect(
      isPathCollapsed(
        { field_1: 'A' },
        { mode: 'expand', paths: [{ field_1: 'A' }] },
        fields
      )
    ).toBe(true)
    expect(
      isPathCollapsed(
        { field_1: 'B' },
        { mode: 'expand', paths: [{ field_1: 'A' }] },
        fields
      )
    ).toBe(false)
    expect(
      isPathCollapsed(
        { field_1: 'A' },
        { mode: 'collapse', paths: [{ field_1: 'A' }] },
        fields
      )
    ).toBe(false)
    expect(
      isPathCollapsed(
        { field_1: 'B' },
        { mode: 'collapse', paths: [{ field_1: 'A' }] },
        fields
      )
    ).toBe(true)
  })
})

describe('gridGroupedRender / getEffectiveRow', () => {
  test('returns the row unchanged when no pending entry exists', () => {
    const row = { id: 1, field_1: 'A' }
    expect(getEffectiveRow(row, new Map())).toBe(row)
  })

  test('overlays the pending patch on top of the row', () => {
    const row = { id: 1, field_1: 'A', field_2: 'unchanged' }
    const pending = new Map([[1, { patch: { field_1: 'B' } }]])
    expect(getEffectiveRow(row, pending)).toEqual({
      id: 1,
      field_1: 'B',
      field_2: 'unchanged',
    })
  })

  test('returns row unchanged when pending entry has no patch', () => {
    const row = { id: 1, field_1: 'A' }
    const pending = new Map([[1, { fromSectionKey: 'X' }]])
    expect(getEffectiveRow(row, pending)).toBe(row)
  })

  test('passes through undefined row', () => {
    expect(getEffectiveRow(undefined, new Map())).toBeUndefined()
  })
})

describe('gridGroupedRender / renderViewport', () => {
  test('viewport covering the whole tree emits every header + every loaded row + addRow trailer', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 2 }],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    const sectionRows = buildSectionRows(
      [
        {
          path: { field_1: 'A' },
          rows: [
            { id: 1, field_1: 'A' },
            { id: 2, field_1: 'A' },
          ],
        },
      ],
      fields
    )
    const items = renderViewport({
      layout,
      sectionRows,
      pending: new Map(),
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields,
    })
    expect(items.map((it) => it.type)).toEqual([
      'header',
      'row',
      'row',
      'addRow',
    ])
    expect(items[1].row.id).toBe(1)
    expect(items[2].row.id).toBe(2)
    expect(items[1].y).toBe(HEADER_HEIGHT)
    expect(items[2].y).toBe(HEADER_HEIGHT + ROW_HEIGHT)
  })

  test('viewport outside a section emits no items for it', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 100 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 1 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    const aRows = Array.from({ length: 100 }, (_, i) => ({
      id: i,
      field_1: 'A',
    }))
    const sectionRows = buildSectionRows(
      [
        { path: { field_1: 'A' }, rows: aRows },
        { path: { field_1: 'B' }, rows: [{ id: 200, field_1: 'B' }] },
      ],
      fields
    )
    const bSectionY = 2 * HEADER_HEIGHT + 100 * ROW_HEIGHT
    const items = renderViewport({
      layout,
      sectionRows,
      pending: new Map(),
      viewport: { scrollTop: bSectionY - HEADER_HEIGHT, clientHeight: 100 },
      fields,
    })
    expect(
      items.filter((it) => it.type === 'row' && it.row.field_1 === 'A')
    ).toHaveLength(0)
    expect(
      items.some((it) => it.type === 'header' && it.path.field_1 === 'B')
    ).toBe(true)
    expect(items.some((it) => it.type === 'row' && it.row.id === 200)).toBe(
      true
    )
  })

  test('row section with missing positions emits placeholders so the layout does not collapse', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    const sectionRows = buildSectionRows(
      [{ path: { field_1: 'A' }, rows: [{ id: 1, field_1: 'A' }] }],
      fields
    )
    const items = renderViewport({
      layout,
      sectionRows,
      pending: new Map(),
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields,
    })
    const slotTypes = items
      .filter((it) => it.type !== 'header' && it.type !== 'addRow')
      .map((it) => it.type)
    expect(slotTypes).toEqual(['row', 'placeholder', 'placeholder'])
  })

  test('collapsed section emits a header only (no rows, no placeholders)', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 3 }],
      collapse: { mode: 'expand', paths: [{ field_1: 'A' }] },
      fields,
    })
    const sectionRows = buildSectionRows(
      [{ path: { field_1: 'A' }, rows: [{ id: 1, field_1: 'A' }] }],
      fields
    )
    const items = renderViewport({
      layout,
      sectionRows,
      pending: new Map(),
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields,
    })
    expect(items.map((it) => it.type)).toEqual(['header'])
  })

  test('pending patch is applied to row data via overlay', () => {
    // The structural move (group-by change) is materialised into the
    // bucket by the store; here we only verify that the pending patch
    // is applied to the row's field data at render time.
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 1 }],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    const sectionRows = buildSectionRows(
      [
        {
          path: { field_1: 'A' },
          rows: [{ id: 1, field_1: 'A', field_2: 'cached' }],
        },
      ],
      fields
    )
    const pending = new Map([[1, { patch: { field_2: 'pending' } }]])
    const items = renderViewport({
      layout,
      sectionRows,
      pending,
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields,
    })
    const row = items.find((it) => it.type === 'row').row
    expect(row.field_2).toBe('pending')
  })

  test('row at section position N renders at correct pixel y', () => {
    // After per-section caching, the row's pixel position is purely
    // derived from its section's pixel y + (position * ROW_HEIGHT).
    // Section A first row sits at HEADER_HEIGHT.
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 5 }],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    // Sparse bucket: row at position 3 only.
    const sectionRows = new Map()
    const bucket = new Map()
    bucket.set(3, { id: 999, field_1: 'A' })
    sectionRows.set(pathKey({ field_1: 'A' }, fields), bucket)
    const items = renderViewport({
      layout,
      sectionRows,
      pending: new Map(),
      viewport: { scrollTop: 0, clientHeight: 10000 },
      fields,
    })
    const rowItem = items.find((it) => it.type === 'row')
    expect(rowItem.row.id).toBe(999)
    expect(rowItem.y).toBe(HEADER_HEIGHT + 3 * ROW_HEIGHT)
  })
})

describe('gridGroupedRender / visibleSectionsInViewport', () => {
  test('returns each section that overlaps the viewport with position bounds', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 5 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 3 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    // Viewport covers all of A's section + addRow trailer + GROUP_GAP
    // + B's header + first 2 rows.
    const aSectionTop = HEADER_HEIGHT
    const ranges = visibleSectionsInViewport(
      layout,
      {
        scrollTop: aSectionTop,
        clientHeight:
          5 * ROW_HEIGHT +
          ROW_HEIGHT + // A's addRow trailer
          GROUP_GAP +
          HEADER_HEIGHT +
          2 * ROW_HEIGHT,
      },
      fields
    )
    expect(ranges).toHaveLength(2)
    expect(ranges[0].sectionKey).toBe(pathKey({ field_1: 'A' }, fields))
    expect(ranges[0].startPosition).toBe(0)
    expect(ranges[0].endPosition).toBe(5)
    expect(ranges[0].firstGlobalRowOffset).toBe(0)
    expect(ranges[1].sectionKey).toBe(pathKey({ field_1: 'B' }, fields))
    expect(ranges[1].startPosition).toBe(0)
    expect(ranges[1].endPosition).toBe(2)
    expect(ranges[1].firstGlobalRowOffset).toBe(5)
  })

  test('viewport entirely inside a section returns just that section with clipped bounds', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, rowCount: 100 }],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    // Viewport covers rows 20..49 (30 rows) of section A.
    const ranges = visibleSectionsInViewport(
      layout,
      {
        scrollTop: HEADER_HEIGHT + 20 * ROW_HEIGHT,
        clientHeight: 30 * ROW_HEIGHT,
      },
      fields
    )
    expect(ranges).toHaveLength(1)
    expect(ranges[0].startPosition).toBe(20)
    expect(ranges[0].endPosition).toBe(50)
  })

  test('collapsed sections do not appear in the result', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, rowCount: 100 },
        { path: { field_1: 'B' }, depth: 0, rowCount: 3 },
      ],
      collapse: { mode: 'expand', paths: [{ field_1: 'A' }] },
      fields,
    })
    // Viewport covers everything visible. A is collapsed → no row
    // section. Only B's rowSection should appear.
    const ranges = visibleSectionsInViewport(
      layout,
      { scrollTop: 0, clientHeight: 10000 },
      fields
    )
    expect(ranges).toHaveLength(1)
    expect(ranges[0].sectionKey).toBe(pathKey({ field_1: 'B' }, fields))
  })
})

describe('gridGroupedRender / pixelToRowOffset + pixelRangeToRowOffsetRange', () => {
  const fields = [textField(1)]
  const layout = buildLayout({
    nodes: [
      { path: { field_1: 'A' }, depth: 0, rowCount: 5 },
      { path: { field_1: 'B' }, depth: 0, rowCount: 3 },
    ],
    collapse: { mode: 'expand', paths: [] },
    fields,
  })
  const aFirstRowY = HEADER_HEIGHT
  // A's banner + 5 rows + 1 addRow trailer + GROUP_GAP + B's banner
  const bFirstRowY =
    2 * HEADER_HEIGHT + 5 * ROW_HEIGHT + ROW_HEIGHT + GROUP_GAP

  test('a pixel inside A`s row section maps to a row offset within A', () => {
    expect(pixelToRowOffset(layout, aFirstRowY)).toBe(0)
    expect(pixelToRowOffset(layout, aFirstRowY + 2 * ROW_HEIGHT + 5)).toBe(2)
    expect(pixelToRowOffset(layout, aFirstRowY + 4 * ROW_HEIGHT)).toBe(4)
  })

  test('a pixel inside B`s row section maps to a row offset continuing from A', () => {
    expect(pixelToRowOffset(layout, bFirstRowY)).toBe(5)
    expect(pixelToRowOffset(layout, bFirstRowY + 2 * ROW_HEIGHT)).toBe(7)
  })

  test('a pixel inside a header snaps to the last row of the previous section', () => {
    // B's banner sits after A's banner + 5 rows + addRow trailer +
    // GROUP_GAP.
    const bBannerY =
      HEADER_HEIGHT + 5 * ROW_HEIGHT + ROW_HEIGHT + GROUP_GAP + 4
    expect(pixelToRowOffset(layout, bBannerY)).toBe(4)
  })

  test('pixelRangeToRowOffsetRange covers every row whose y range overlaps the viewport', () => {
    const top = aFirstRowY + 2 * ROW_HEIGHT
    const bottom = bFirstRowY + 2 * ROW_HEIGHT
    const { startOffset, endOffset } = pixelRangeToRowOffsetRange(
      layout,
      top,
      bottom
    )
    expect(startOffset).toBe(2)
    expect(endOffset).toBeGreaterThanOrEqual(6)
    expect(endOffset).toBeLessThanOrEqual(8)
  })

  test('empty tree returns a zero-length range', () => {
    const empty = buildLayout({
      nodes: [],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    const range = pixelRangeToRowOffsetRange(empty, 0, 1000)
    expect(range).toEqual({ startOffset: 0, endOffset: 0 })
  })
})
