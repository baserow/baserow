import { TestApp } from '@baserow/test/helpers/testApp'
import { firstBy } from 'thenby'

const A = { id: 1, value: 'A', color: 'blue', order: 0 }
const B = { id: 2, value: 'B', color: 'yellow', order: 1 }
const C = { id: 3, value: 'C', color: 'red', order: 2 }

const field = {
  id: 99,
  select_options: [A, B, C],
}

describe('MultipleSelectFieldType.getGroupBySort()', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('cells with the same options sort together regardless of pick order', () => {
    const fieldType = testApp._app.$registry.get('field', 'multiple_select')
    const rows = [
      { id: 1, order: '1.00000000000000000000', field: [A, C] },
      { id: 2, order: '2.00000000000000000000', field: [B] },
      // Same set as row 1, picked the other way round.
      { id: 3, order: '3.00000000000000000000', field: [C, A] },
      { id: 4, order: '4.00000000000000000000', field: [] },
    ]

    const ASC = fieldType.getGroupBySort('field', 'ASC', field)
    expect(ASC(rows[0], rows[2])).toBe(0)

    rows.sort(firstBy().thenBy(ASC))
    // ASC by [order, id]: empty < {A,C} ([0,1],[2,3]) < {B} ([1,2])
    expect(rows.map((row) => row.id)).toEqual([4, 1, 3, 2])

    const DESC = fieldType.getGroupBySort('field', 'DESC', field)
    rows.sort(firstBy().thenBy(DESC))
    expect(rows.map((row) => row.id)).toEqual([2, 1, 3, 4])
  })

  test('handles unhydrated { id } objects by resolving from field options', () => {
    const fieldType = testApp._app.$registry.get('field', 'multiple_select')
    const rows = [
      { id: 1, order: '1.00000000000000000000', field: [{ id: 3 }, { id: 1 }] },
      { id: 2, order: '2.00000000000000000000', field: [{ id: 1 }, { id: 3 }] },
      { id: 3, order: '3.00000000000000000000', field: [{ id: 2 }] },
    ]

    const ASC = fieldType.getGroupBySort('field', 'ASC', field)
    expect(ASC(rows[0], rows[1])).toBe(0)

    rows.sort(firstBy().thenBy(ASC))
    // {A,C} ([0,1],[2,3]) < {B} ([1,2])
    expect(rows.map((row) => row.id)).toEqual([1, 2, 3])
  })

  test('handles null and undefined values without crashing', () => {
    const fieldType = testApp._app.$registry.get('field', 'multiple_select')
    const rows = [
      { id: 1, order: '1.00000000000000000000', field: [A] },
      { id: 2, order: '2.00000000000000000000', field: null },
      { id: 3, order: '3.00000000000000000000', field: undefined },
      { id: 4, order: '4.00000000000000000000', field: [] },
    ]

    const ASC = fieldType.getGroupBySort('field', 'ASC', field)
    rows.sort(firstBy().thenBy(ASC))
    // empty/null/undefined all produce [] which sorts before [A]
    expect(rows.map((row) => row.id)).toEqual([2, 3, 4, 1])
  })

  test('sorts groups by field-defined option order, not alphabetically', () => {
    const fieldType = testApp._app.$registry.get('field', 'multiple_select')
    // Options with non-alphabetical order: Z first, A second
    const Z = { id: 10, value: 'Zebra', color: 'blue', order: 0 }
    const aOpt = { id: 11, value: 'Apple', color: 'red', order: 1 }
    const customField = { id: 100, select_options: [Z, aOpt] }

    const rows = [
      { id: 1, order: '1.00000000000000000000', field: [aOpt] },
      { id: 2, order: '2.00000000000000000000', field: [Z] },
    ]

    const ASC = fieldType.getGroupBySort('field', 'ASC', customField)
    rows.sort(firstBy().thenBy(ASC))
    // Zebra has order=0, Apple has order=1, so Zebra group comes first
    expect(rows.map((row) => row.id)).toEqual([2, 1])
  })
})
