import {
  HEADER_HEIGHT,
  ROW_HEIGHT,
  ADD_ROW_HEIGHT,
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

  test('pathKey treats m2m id arrays as a set (order-insensitive)', () => {
    const fields = [{ id: 2, type: 'multiple_collaborators' }]
    expect(pathKey({ field_2: [8, 6, 7] }, fields)).toBe(
      pathKey({ field_2: [6, 7, 8] }, fields)
    )
    // Different sets still produce different keys.
    expect(pathKey({ field_2: [6, 7] }, fields)).not.toBe(
      pathKey({ field_2: [6, 8] }, fields)
    )
  })

  // An optimistically-emptied group keeps its node (for reconciliation) at row_count 0,
  // but its banner must not be rendered. Covers each group-value shape.
  describe.each([
    { name: 'collaborator', empty: [100], full: [200] },
    { name: 'link row', empty: [100], full: [200] },
    { name: 'multiple select', empty: [100], full: [200] },
    { name: 'single select', empty: 100, full: 200 },
  ])('hides emptied $name groups', ({ empty, full }) => {
    const fields = [{ id: 2, type: 'group' }]
    const visibleHeaderKeys = (layout) =>
      layout.items
        .filter((item) => item.type === 'header')
        .map((item) => pathKey(item.path, fields))

    test('tree layout', () => {
      const layout = buildLayout({
        nodes: [
          { path: { field_2: empty }, depth: 0, row_count: 0 },
          { path: { field_2: full }, depth: 0, row_count: 2 },
        ],
        collapse: { mode: 'expand', paths: [] },
        fields,
      })
      expect(visibleHeaderKeys(layout)).toEqual([
        pathKey({ field_2: full }, fields),
      ])
    })

    test('paged layout', () => {
      const layout = buildLayout({
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 2,
            nodes: {
              0: {
                path: { field_2: empty },
                depth: 0,
                row_count: 0,
                sibling_index: 0,
                row_offset: 0,
              },
              1: {
                path: { field_2: full },
                depth: 0,
                row_count: 2,
                sibling_index: 1,
                row_offset: 0,
              },
            },
          },
        },
        collapse: { mode: 'expand', paths: [] },
        fields,
      })
      expect(visibleHeaderKeys(layout)).toEqual([
        pathKey({ field_2: full }, fields),
      ])
      // The remaining group becomes the first visible one, so no leading gap.
      const header = layout.items.find((item) => item.type === 'header')
      expect(header.y).toBe(0)
    })
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

  test('an empty loaded paged layout keeps a top-level add-row line', () => {
    const fields = [textField(1)]

    const layout = buildLayout({
      pages: {
        '': { parentPath: {}, totalSiblingCount: 0, nodes: {} },
      },
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    expect(layout.items).toEqual([
      { type: 'addRow', depth: 0, path: {}, y: 0, height: ADD_ROW_HEIGHT },
    ])
    expect(layout.totalHeight).toBe(ADD_ROW_HEIGHT)
    expect(layout.totalRowCount).toBe(0)

    // A tree without a loaded root page renders nothing, so the add-row line
    // doesn't flash while the first request is in flight.
    const unloaded = buildLayout({
      pages: {},
      collapse: { mode: 'expand', paths: [] },
      fields,
    })
    expect(unloaded.items).toEqual([])
  })

  test('add-row trailers keep the small height when the view row height is larger', () => {
    const fields = [textField(1)]
    const rowHeight = 99

    const treeLayout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, row_count: 2 }],
      collapse: { mode: 'expand', paths: [] },
      fields,
      rowHeight,
    })
    const [, treeSection, treeAddRow] = treeLayout.items
    expect(treeSection.height).toBe(2 * rowHeight)
    expect(treeAddRow.height).toBe(ADD_ROW_HEIGHT)
    expect(treeAddRow.y).toBe(HEADER_HEIGHT + 2 * rowHeight)
    expect(treeLayout.totalHeight).toBe(
      HEADER_HEIGHT + 2 * rowHeight + ADD_ROW_HEIGHT
    )

    const pagedLayout = buildLayout({
      pages: {
        '': {
          parentPath: {},
          totalSiblingCount: 1,
          nodes: {
            0: {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 2,
              sibling_index: 0,
              row_offset: 0,
            },
          },
        },
      },
      collapse: { mode: 'expand', paths: [] },
      fields,
      rowHeight,
    })
    const pagedAddRow = pagedLayout.items.find((item) => item.type === 'addRow')
    expect(pagedAddRow.height).toBe(ADD_ROW_HEIGHT)
    expect(pagedAddRow.y).toBe(HEADER_HEIGHT + 2 * rowHeight)
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

  test('sibling sub-groups get a gap while a first child stays flush', () => {
    const fields = [textField(1), textField(2)]
    const layout = buildLayout({
      nodes: [
        { path: { field_1: 'A' }, depth: 0, row_count: 2 },
        { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 1 },
        { path: { field_1: 'A', field_2: 'Y' }, depth: 1, row_count: 1 },
      ],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })

    const headerFor = (value) =>
      layout.items.find(
        (item) => item.type === 'header' && item.path.field_2 === value
      )
    expect(headerFor('X').y).toBe(HEADER_HEIGHT)
    expect(headerFor('X').gapAbove).toBe(false)
    expect(headerFor('Y').y).toBe(
      2 * HEADER_HEIGHT + ROW_HEIGHT + ROW_HEIGHT + GROUP_GAP
    )
    expect(headerFor('Y').gapAbove).toBe(true)
  })

  test('the paged layout also separates sibling sub-groups with a gap', () => {
    const fields = [textField(1), textField(2)]
    const parentKey = pathKey({ field_1: 'A' }, fields)
    const leaf = (index, value) => ({
      path: { field_1: 'A', field_2: value },
      depth: 1,
      row_count: 1,
      sibling_index: index,
      row_offset: index,
    })
    const layout = buildLayout({
      pages: {
        '': {
          totalSiblingCount: 1,
          nodes: {
            0: {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 2,
              children_count: 2,
              sibling_index: 0,
              row_offset: 0,
            },
          },
        },
        [parentKey]: {
          totalSiblingCount: 2,
          nodes: { 0: leaf(0, 'X'), 1: leaf(1, 'Y') },
        },
      },
      collapse: { mode: 'expand', paths: [] },
      fields,
      pageSize: 40,
    })

    const headerFor = (value) =>
      layout.items.find(
        (item) => item.type === 'header' && item.path.field_2 === value
      )
    expect(headerFor('X').gapAbove).toBe(false)
    expect(headerFor('Y').gapAbove).toBe(true)
    expect(headerFor('Y').y).toBe(
      2 * HEADER_HEIGHT + ROW_HEIGHT + ROW_HEIGHT + GROUP_GAP
    )
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
          globalSiblingStartIndex: 0,
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
          globalSiblingStartIndex: 10,
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
          globalSiblingStartIndex: 0,
          y: 0,
          height: firstPageHeight,
        },
        {
          type: 'groupPlaceholder',
          parentPath: {},
          depth: 0,
          siblingStartIndex: 40,
          siblingEndIndex: 80,
          globalSiblingStartIndex: 40,
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

  test('visibleGroupDepthPageInViewport counts hidden emptied leaf groups toward the depth offset', () => {
    const fields = [textField(1), textField(2)]
    const parentKey = pathKey({ field_1: 'A' }, fields)
    const leaf = (index, rowCount) => ({
      path: { field_1: 'A', field_2: `v${index}` },
      depth: 1,
      row_count: rowCount,
      sibling_index: index,
      row_offset: index,
    })
    const layout = buildLayout({
      pages: {
        '': {
          totalSiblingCount: 1,
          nodes: {
            0: {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 3,
              children_count: 8,
              sibling_index: 0,
              row_offset: 0,
            },
          },
        },
        [parentKey]: {
          totalSiblingCount: 8,
          // Index 1 is optimistically emptied (row_count 0) and hidden, but it still
          // occupies a sibling slot the server counts, so the placeholder that follows
          // starts at global sibling index 4, not 3.
          nodes: {
            0: leaf(0, 1),
            1: leaf(1, 0),
            2: leaf(2, 1),
            3: leaf(3, 1),
          },
        },
      },
      collapse: { mode: 'expand', paths: [] },
      fields,
      pageSize: 4,
    })

    const placeholder = layout.items.find(
      (item) => item.type === 'groupPlaceholder'
    )
    expect(placeholder.siblingStartIndex).toBe(4)
    expect(placeholder.globalSiblingStartIndex).toBe(4)

    expect(
      visibleGroupDepthPageInViewport(
        layout,
        { scrollTop: placeholder.y, clientHeight: HEADER_HEIGHT },
        4
      )
    ).toEqual({ depth: 1, offset: 4, limit: 4 })
  })

  test('display values propagate from tree nodes into header items', () => {
    const fields = [textField(1)]
    const display = { field_1: [{ id: 10, name: 'Davide' }] }
    const layout = buildLayout({
      nodes: [{ path: { field_1: 'A' }, depth: 0, row_count: 1, display }],
      collapse: { mode: 'expand', paths: [] },
      fields,
    })

    const header = layout.items.find((item) => item.type === 'header')
    expect(header.display).toEqual(display)
  })

  test('display values survive the paged layout and the rendered viewport', () => {
    const fields = [textField(1)]
    const display = { field_1: [{ id: 10, name: 'Davide' }] }
    const layout = buildLayout({
      pages: {
        '': {
          totalSiblingCount: 1,
          nodes: {
            0: {
              path: { field_1: 'A' },
              depth: 0,
              row_count: 1,
              sibling_index: 0,
              row_offset: 0,
              display,
            },
          },
        },
      },
      collapse: { mode: 'expand', paths: [] },
      fields,
      pageSize: 40,
    })

    const layoutHeader = layout.items.find((item) => item.type === 'header')
    expect(layoutHeader.display).toEqual(display)

    const items = renderViewport({
      layout,
      sectionRows: buildSectionRows(
        [{ path: { field_1: 'A' }, rows: [] }],
        fields
      ),
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields,
    })
    const renderedHeader = items.find((item) => item.type === 'header')
    expect(renderedHeader.display).toEqual(display)
  })
})

describe('buildLayout cycle safety', () => {
  test('does not overflow the stack when a stale page resolves to its own key', () => {
    // Reproduces the "too much recursion" crash: a deleted mid group-by field leaves
    // the layout fields ([2, 4]) out of step with the keys baked into the still-present
    // pages, so pathKey truncates and the child page of {field_2: 'A'} resolves back to
    // its own key with a depth that never reaches maxDepth. Without a guard walkPage
    // recurses forever.
    const fields = [textField(2), textField(4)]
    const node = {
      path: { field_2: 'A' },
      depth: 0,
      children_count: 1,
      row_count: 2,
    }
    const pages = {
      '': { parentPath: {}, totalSiblingCount: 1, nodes: { 0: node } },
      [pathKey({ field_2: 'A' }, fields)]: {
        totalSiblingCount: 1,
        nodes: { 0: node },
      },
    }

    expect(() =>
      buildLayout({
        nodes: null,
        pages,
        collapse: { mode: 'expand', paths: [] },
        fields,
      })
    ).not.toThrow()
  })
})

describe('renderViewport group skeletons', () => {
  // Sibling groups are separated by a gap at every depth; a range starting at the
  // parent's first child has no gap above its first slot.
  const placeholderLayout = (depth, count) => ({
    items: [
      {
        type: 'groupPlaceholder',
        parentPath: {},
        depth,
        siblingStartIndex: 0,
        siblingEndIndex: count,
        y: 0,
        height: count * HEADER_HEIGHT + (count - 1) * GROUP_GAP,
      },
    ],
    totalHeight: count * HEADER_HEIGHT + (count - 1) * GROUP_GAP,
    totalRowCount: 0,
  })

  test('renders unloaded group placeholders as skeleton headers', () => {
    const items = renderViewport({
      layout: placeholderLayout(1, 3),
      sectionRows: new Map(),
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields: [textField(1), textField(2)],
    })
    const skeletons = items.filter((item) => item.type === 'groupSkeleton')
    expect(skeletons).toHaveLength(3)
    expect(skeletons.every((s) => s.depth === 1)).toBe(true)
    expect(skeletons.map((s) => s.y)).toEqual([
      0,
      HEADER_HEIGHT + GROUP_GAP,
      2 * (HEADER_HEIGHT + GROUP_GAP),
    ])
  })

  test('walks the skeleton through every nested level the group still has', () => {
    const items = renderViewport({
      layout: placeholderLayout(1, 4),
      sectionRows: new Map(),
      viewport: { scrollTop: 0, clientHeight: 1000 },
      fields: [textField(1), textField(2), textField(3)],
    })
    const skeletons = items.filter((item) => item.type === 'groupSkeleton')
    // 3 levels (maxDepth 2) with the placeholder at depth 1, so the staircase cycles
    // through the remaining levels 1 and 2.
    expect(skeletons.map((s) => s.depth)).toEqual([1, 2, 1, 2])
  })

  test('clips skeletons to the viewport instead of rendering the whole range', () => {
    const items = renderViewport({
      layout: placeholderLayout(0, 500),
      sectionRows: new Map(),
      viewport: { scrollTop: 0, clientHeight: 2 * HEADER_HEIGHT },
      fields: [textField(1)],
    })
    const skeletons = items.filter((item) => item.type === 'groupSkeleton')
    expect(skeletons.length).toBeGreaterThan(0)
    expect(skeletons.length).toBeLessThanOrEqual(3)
  })
})
