import { fitGroupByWidths } from '@baserow/modules/database/utils/gridGroupByWidths'

describe('fitGroupByWidths', () => {
  test('keeps configured widths when they fit or the grid is not measured', () => {
    const groupBys = [{ width: 90 }, { width: 180 }, { width: 270 }]

    expect(fitGroupByWidths(groupBys, 600, 78)).toEqual([90, 180, 270])
    expect(fitGroupByWidths(groupBys, null, 78)).toEqual([90, 180, 270])
  })

  test('scales only space above the minimum and does not mutate configured widths', () => {
    const groupBys = [
      { width: 78 },
      { width: 120 },
      { width: 200 },
      { width: 260 },
      { width: 342 },
    ]
    const configuredWidths = groupBys.map(({ width }) => width)
    const renderedWidths = fitGroupByWidths(groupBys, 652, 78)

    expect(renderedWidths[0]).toBe(78)
    expect(renderedWidths.every((width) => width >= 78)).toBe(true)
    expect(
      renderedWidths.reduce((total, width) => total + width, 0)
    ).toBeCloseTo(652)
    expect(groupBys.map(({ width }) => width)).toEqual(configuredWidths)
  })
})
