import {
  HEADER_HEIGHT,
  ROW_HEIGHT,
  GROUP_GAP,
  buildLayout,
  pathKey,
  isPathCollapsed,
  renderViewport,
  visibleSectionsInViewport,
} from '@baserow/modules/database/utils/gridGroupByRender'

const textField = (id) => ({ id, name: `field ${id}`, type: 'text' })

const buildSectionRows = (entries, fields) => {
  const map = new Map()
  for (const { path, rows } of entries) {
    const bucket = new Map()
    rows.forEach((row, position) => bucket.set(position, row))
    map.set(pathKey(path, fields), bucket)
  }
  return map
}

describe('gridGroupByRender', () => {
  test('pathKey is stable and depth-aware', () => {
    expect(
      pathKey({ field_2: 'B', field_1: 'A' }, [textField(1), textField(2)])
    ).toBe(
      pathKey({ field_1: 'A', field_2: 'B' }, [textField(1), textField(2)])
    )
    expect(pathKey({ field_1: 'A' }, [textField(1)])).not.toBe(
      pathKey({ field_1: 'A', field_2: 'B' }, [textField(1), textField(2)])
    )
  })

  test('isPathCollapsed supports expand and collapse modes', () => {
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
        { field_1: 'A' },
        { mode: 'collapse', paths: [{ field_1: 'A' }] },
        fields
      )
    ).toBe(false)
  })

  test('buildLayout emits headers, leaf row sections, and add-row trailers', () => {
    const fields = [textField(1), textField(2)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, row_count: 3 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 2 },
        { path: { field_1: 'A', field_2: 'Y' }, depth: 1, row_count: 1 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })

    expect(layout.items.map((item) => item.type)).toEqual([
      'header',
      'header',
      'rowSection',
      'addRow',
      'header',
      'rowSection',
      'addRow',
    ])
    expect(layout.totalRowCount).toBe(3)
    expect(layout.items.filter((item) => item.type === 'rowSection')).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ rowCount: 2, firstGlobalRowOffset: 0 }),
        expect.objectContaining({ rowCount: 1, firstGlobalRowOffset: 2 }),
      ])
    )
  })

  test('buildLayout skips collapsed descendants', () => {
    const fields = [textField(1), textField(2)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, row_count: 3 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 2 },
        { path: { field_1: 'B' }, depth: 0, row_count: 1 },
        { path: { field_1: 'B', field_2: 'X' }, depth: 1, row_count: 1 },
      ],
      collapse: { mode: 'expand', paths: [{ field_1: 'A' }] },
      fields,
    })

    expect(
      layout.items.filter((item) => item.path.field_1 === 'A')
    ).toHaveLength(1)
    expect(layout.totalRowCount).toBe(1)
  })

  test('visibleSectionsInViewport returns section-local ranges', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, row_count: 5 },
        { path: { field_1: 'B' }, depth: 0, row_count: 3 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })

    const ranges = visibleSectionsInViewport(
      layout,
      {
        scrollTop: HEADER_HEIGHT + 2 * ROW_HEIGHT,
        clientHeight: 5 * ROW_HEIGHT + ROW_HEIGHT + GROUP_GAP + HEADER_HEIGHT,
      },
      fields
    )

    expect(ranges).toEqual([
      expect.objectContaining({
        sectionKey: pathKey({ field_1: 'A' }, fields),
        startPosition: 2,
        endPosition: 5,
        firstGlobalRowOffset: 0,
      }),
      expect.objectContaining({
        sectionKey: pathKey({ field_1: 'B' }, fields),
        startPosition: 0,
        firstGlobalRowOffset: 5,
      }),
    ])
  })

  test('renderViewport renders rows and placeholders from section buckets', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, row_count: 3 }],
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
      pending: new Map([[1, { patch: { field_2: 'pending' } }]]),
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields,
    })

    expect(items.map((item) => item.type)).toEqual([
      'header',
      'row',
      'placeholder',
      'placeholder',
      'addRow',
    ])
    expect(items.find((item) => item.type === 'row').row.field_2).toBe(
      'pending'
    )
  })

  test('top-level groups get a visual gap after the first group', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, row_count: 1 },
        { path: { field_1: 'B' }, depth: 0, row_count: 1 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })

    const bHeader = layout.items.find(
      (item) => item.type === 'header' && item.path.field_1 === 'B'
    )
    expect(bHeader.y).toBe(HEADER_HEIGHT + ROW_HEIGHT + ROW_HEIGHT + GROUP_GAP)
  })
})
