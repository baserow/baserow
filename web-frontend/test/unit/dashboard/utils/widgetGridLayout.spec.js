import {
  createWidgetGridLayout,
  getDashboardGridColumns,
  getWidgetGridItemConstraints,
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
  test('selects a layout from the available container width', () => {
    expect(getDashboardGridColumns(920)).toBe(6)
    expect(getDashboardGridColumns(700)).toBe(4)
    expect(getDashboardGridColumns(599)).toBe(1)
  })

  test('keeps the canonical six-column layout', () => {
    const layout = createWidgetGridLayout(
      [summary(2, 2, 0, 4, 4), summary(1, 0, 0, 2, 4)],
      6
    )

    expect(layout).toEqual([
      { i: 1, x: 0, y: 0, w: 2, h: 4 },
      { i: 2, x: 2, y: 0, w: 4, h: 4 },
    ])
  })

  test('projects a two-plus-four row to four columns', () => {
    const layout = createWidgetGridLayout(
      [summary(1, 0, 0, 2, 4), summary(2, 2, 0, 4, 4)],
      4
    )

    expect(layout).toEqual([
      { i: 1, x: 0, y: 0, w: 1, h: 4 },
      { i: 2, x: 1, y: 0, w: 3, h: 4 },
    ])
  })

  test('stacks widgets on mobile without persisting the projection', () => {
    const layout = createWidgetGridLayout(
      [summary(1, 0, 0, 2, 4), summary(2, 2, 0, 4, 4)],
      1
    )

    expect(layout).toEqual([
      { i: 1, x: 0, y: 0, w: 1, h: 4 },
      { i: 2, x: 0, y: 4, w: 1, h: 4 },
    ])
  })

  test('uses visual constraints that fit a projected widget', () => {
    const chart = {
      grid_layout: {
        min_width: 3,
        min_height: 8,
        max_width: 6,
        max_height: 16,
      },
    }

    expect(
      getWidgetGridItemConstraints(chart, 4, { i: 1, x: 0, y: 0, w: 2, h: 9 })
    ).toEqual({ minW: 2, minH: 8, maxW: 4, maxH: 16 })
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
})
