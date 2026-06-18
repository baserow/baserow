import {
  HEADER_HEIGHT,
  ROW_HEIGHT,
  GROUP_GAP,
  buildLayout,
  pathKey,
  renderViewport,
  visibleGroupDepthPageInViewport,
  visibleGroupPagesInViewport,
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
    expect(pathKey({ field_1: 'A' }, [textField(1)])).not.toBe(
      pathKey({ field_2: 'A' }, [textField(2)])
    )
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

  test('buildLayout collapses only the exact path in expand mode', () => {
    const fields = [textField(1), textField(2)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, row_count: 3 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 2 },
        { path: { field_1: 'A', field_2: 'Y' }, depth: 1, row_count: 1 },
      ],
      collapse: {
        mode: 'expand',
        paths: [{ field_1: 'A', field_2: 'X' }],
      },
      fields,
    })

    expect(
      layout.items.find((item) => item.path.field_1 === 'A').collapsed
    ).toBe(false)
    expect(
      layout.items.find((item) => item.path.field_2 === 'X').collapsed
    ).toBe(true)
    expect(
      layout.items.some(
        (item) => item.type === 'rowSection' && item.path.field_2 === 'Y'
      )
    ).toBe(true)
  })

  test('buildLayout expands path prefixes in collapse mode', () => {
    const fields = [textField(1), textField(2)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, row_count: 3 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 2 },
        { path: { field_1: 'A', field_2: 'Y' }, depth: 1, row_count: 1 },
      ],
      collapse: {
        mode: 'collapse',
        paths: [{ field_1: 'A', field_2: 'X' }],
      },
      fields,
    })

    expect(
      layout.items.find((item) => item.path.field_1 === 'A').collapsed
    ).toBe(false)
    expect(
      layout.items.find((item) => item.path.field_2 === 'X').collapsed
    ).toBe(false)
    expect(
      layout.items.some(
        (item) => item.type === 'rowSection' && item.path.field_2 === 'X'
      )
    ).toBe(true)
    expect(
      layout.items.some(
        (item) => item.type === 'rowSection' && item.path.field_2 === 'Y'
      )
    ).toBe(false)
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
    expect(items.find((item) => item.type === 'row').row.id).toBe(1)
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

  test('buildLayout supports sparse paged group data', () => {
    const fields = [textField(1)]
    const layout = buildLayout({
      pages: {
        '': {
          totalSiblingCount: 80,
          nodes: {
            40: {
              path: { field_1: 'Loaded' },
              depth: 0,
              row_count: 1,
              sibling_index: 40,
              row_offset: 40,
            },
          },
        },
      },
      collapse: { mode: 'collapse', paths: [{ field_1: 'Loaded' }] },
      fields,
      pageSize: 40,
    })

    expect(layout.items.map((item) => item.type)).toEqual([
      'groupPlaceholder',
      'header',
      'rowSection',
      'addRow',
      'groupPlaceholder',
    ])
    expect(layout.items.find((item) => item.type === 'rowSection')).toEqual(
      expect.objectContaining({
        absoluteRowOffset: 40,
        firstGlobalRowOffset: 0,
      })
    )
    expect(
      visibleGroupPagesInViewport(
        layout,
        { scrollTop: 0, clientHeight: HEADER_HEIGHT },
        40
      )
    ).toEqual([{ parentPath: {}, offset: 0, limit: 40 }])
  })

  test('visibleGroupDepthPageInViewport returns the global depth page offset', () => {
    const layout = {
      items: [
        { type: 'header', depth: 0, y: 0, height: HEADER_HEIGHT },
        {
          type: 'groupPlaceholder',
          parentPath: { field_1: 'A' },
          depth: 1,
          siblingStartIndex: 0,
          siblingEndIndex: 10,
          y: HEADER_HEIGHT,
          height: 10 * HEADER_HEIGHT,
        },
        {
          type: 'header',
          depth: 0,
          y: 11 * HEADER_HEIGHT,
          height: HEADER_HEIGHT,
        },
        {
          type: 'groupPlaceholder',
          parentPath: { field_1: 'B' },
          depth: 1,
          siblingStartIndex: 0,
          siblingEndIndex: 100,
          y: 12 * HEADER_HEIGHT,
          height: 100 * HEADER_HEIGHT,
        },
      ],
    }

    expect(
      visibleGroupDepthPageInViewport(
        layout,
        {
          scrollTop: 17 * HEADER_HEIGHT,
          clientHeight: HEADER_HEIGHT,
        },
        40
      )
    ).toEqual({
      depth: 1,
      offset: 0,
      limit: 40,
    })

    expect(
      visibleGroupDepthPageInViewport(
        layout,
        {
          scrollTop: 55 * HEADER_HEIGHT,
          clientHeight: HEADER_HEIGHT,
        },
        40
      )
    ).toEqual({
      depth: 1,
      offset: 40,
      limit: 40,
    })
  })

  test('visibleGroupDepthPageInViewport accounts for top-level group gaps', () => {
    const firstPageHeight = 40 * HEADER_HEIGHT + 39 * GROUP_GAP
    const secondPageHeight = 40 * HEADER_HEIGHT + 40 * GROUP_GAP
    const layout = {
      items: [
        {
          type: 'groupPlaceholder',
          parentPath: {},
          depth: 0,
          siblingStartIndex: 0,
          siblingEndIndex: 40,
          y: 0,
          height: firstPageHeight,
        },
        {
          type: 'groupPlaceholder',
          parentPath: {},
          depth: 0,
          siblingStartIndex: 40,
          siblingEndIndex: 80,
          y: firstPageHeight,
          height: secondPageHeight,
        },
      ],
    }

    expect(
      visibleGroupDepthPageInViewport(
        layout,
        {
          scrollTop:
            firstPageHeight + 35 * (HEADER_HEIGHT + GROUP_GAP) + GROUP_GAP,
          clientHeight: HEADER_HEIGHT,
        },
        40
      )
    ).toEqual({
      depth: 0,
      offset: 40,
      limit: 40,
    })
  })
})
