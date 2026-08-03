import { TestApp } from '@baserow/test/helpers/testApp'
import { firstBy } from 'thenby'

const A = { id: 1, value: 'A', color: 'blue' }
const B = { id: 2, value: 'B', color: 'yellow' }
const C = { id: 3, value: 'C', color: 'red' }

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
    expect(rows.map((row) => row.id)).toEqual([4, 1, 3, 2])

    // "B" sorts above "A,C", and the tied rows 1 and 3 keep their relative order.
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
    expect(rows.map((row) => row.id)).toEqual([2, 3, 4, 1])
  })
})
