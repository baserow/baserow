import {
  createWidgetGridLayout,
  getWidgetGridItemConstraints,
  resizeWidgetGridLayout,
  toWidgetLayoutPayload,
} from '@baserow/modules/dashboard/utils/widgetGridLayout'

const summary = (id, gridX, gridY, gridWidth, gridHeight) => ({
  id,
  grid_x: gridX,
  grid_y: gridY,
  grid_width: gridWidth,
  grid_height: gridHeight,
  grid_layout: {
    min_width: 1,
    min_height: 4,
    max_width: 6,
    max_height: 6,
  },
})

describe('widgetGridLayout', () => {
  test('keeps the canonical six-column layout', () => {
    const layout = createWidgetGridLayout([
      summary(2, 2, 0, 4, 4),
      summary(1, 0, 0, 2, 4),
    ])

    expect(layout).toEqual([
      { i: 1, x: 0, y: 0, w: 2, h: 4 },
      { i: 2, x: 2, y: 0, w: 4, h: 4 },
    ])
  })

  test('reflows out-of-bounds and overlapping widgets without hiding them', () => {
    const layout = createWidgetGridLayout([
      summary(1, 0, 0, 3, 4),
      summary(2, 3, 0, 3, 4),
      summary(3, 6, 0, 3, 4),
      summary(4, 9, 0, 3, 4),
    ])

    expect(layout).toEqual([
      { i: 1, x: 0, y: 0, w: 3, h: 4 },
      { i: 2, x: 3, y: 0, w: 3, h: 4 },
      { i: 3, x: 0, y: 4, w: 3, h: 4 },
      { i: 4, x: 3, y: 4, w: 3, h: 4 },
    ])
  })

  test('projects two columns in visual order without filling earlier gaps', () => {
    const widgets = [
      summary(5, 4, 20, 2, 4),
      summary(3, 3, 8, 3, 5),
      summary(1, 0, 0, 2, 4),
      summary(4, 0, 20, 1, 4),
      summary(2, 2, 0, 4, 8),
    ]
    const saved = structuredClone(widgets)

    expect(createWidgetGridLayout(widgets, 2)).toEqual([
      { i: 1, x: 0, y: 0, w: 1, h: 4 },
      { i: 2, x: 0, y: 4, w: 2, h: 8 },
      { i: 3, x: 0, y: 12, w: 1, h: 5 },
      { i: 4, x: 1, y: 12, w: 1, h: 4 },
      { i: 5, x: 0, y: 17, w: 1, h: 4 },
    ])
    expect(widgets).toEqual(saved)
  })

  test('starts each row below its tallest widget', () => {
    expect(
      createWidgetGridLayout(
        [
          summary(1, 0, 0, 3, 4),
          summary(2, 3, 0, 3, 9),
          summary(3, 0, 4, 3, 4),
          summary(4, 3, 9, 3, 4),
        ],
        2
      )
    ).toEqual([
      { i: 1, x: 0, y: 0, w: 1, h: 4 },
      { i: 2, x: 1, y: 0, w: 1, h: 9 },
      { i: 3, x: 0, y: 9, w: 1, h: 4 },
      { i: 4, x: 1, y: 9, w: 1, h: 4 },
    ])
  })

  test('stacks every width on mobile while preserving saved heights', () => {
    expect(
      createWidgetGridLayout(
        [summary(2, 3, 10, 3, 9), summary(1, 0, 0, 6, 16)],
        1
      )
    ).toEqual([
      { i: 1, x: 0, y: 0, w: 1, h: 16 },
      { i: 2, x: 0, y: 16, w: 1, h: 9 },
    ])
  })

  test('allows resizing an existing widget smaller than its current type minimum', () => {
    const chart = {
      grid_layout: {
        min_width: 3,
        min_height: 8,
        max_width: 6,
        max_height: 16,
      },
    }

    expect(
      getWidgetGridItemConstraints(chart, { i: 1, x: 0, y: 0, w: 2, h: 9 })
    ).toEqual({ minW: 2, minH: 8, maxW: 6, maxH: 16 })
  })

  test('serializes a Grid Layout Plus layout for the canonical API', () => {
    expect(
      toWidgetLayoutPayload([{ i: '12', x: 2, y: 4, w: 3, h: 9 }])
    ).toEqual([
      {
        id: 12,
        grid_x: 2,
        grid_y: 4,
        grid_width: 3,
        grid_height: 9,
      },
    ])
  })

  test.each([
    [3, { i: 2, x: 3, y: 0, w: 2, h: 4 }],
    [5, { i: 2, x: 2, y: 4, w: 2, h: 4 }],
    [2, { i: 2, x: 2, y: 0, w: 2, h: 4 }],
  ])(
    'resizes to %s columns, using the right-hand space before moving down',
    (width, neighbor) => {
      const layout = createWidgetGridLayout([
        summary(1, 0, 0, 2, 4),
        summary(2, 2, 0, 2, 4),
      ])
      const original = layout.map((item) => ({ ...item }))

      expect(resizeWidgetGridLayout(layout, 1, width, 4)).toEqual([
        { i: 1, x: 0, y: 0, w: width, h: 4 },
        neighbor,
      ])
      expect(layout).toEqual(original)
    }
  )

  test('keeps a vertical resize in the original columns', () => {
    const layout = createWidgetGridLayout([
      summary(1, 0, 0, 2, 4),
      summary(2, 0, 4, 2, 4),
    ])

    expect(resizeWidgetGridLayout(layout, 1, 2, 6)).toEqual([
      { i: 1, x: 0, y: 0, w: 2, h: 6 },
      { i: 2, x: 0, y: 6, w: 2, h: 4 },
    ])
  })

  test('pushes a row of neighbors right, then down at the grid edge', () => {
    const layout = createWidgetGridLayout([
      summary(1, 0, 0, 2, 4),
      summary(2, 2, 0, 2, 4),
      summary(3, 4, 0, 2, 4),
    ])

    expect(resizeWidgetGridLayout(layout, 1, 3, 4)).toEqual([
      { i: 1, x: 0, y: 0, w: 3, h: 4 },
      { i: 2, x: 3, y: 0, w: 2, h: 4 },
      { i: 3, x: 4, y: 4, w: 2, h: 4 },
    ])
  })
})
