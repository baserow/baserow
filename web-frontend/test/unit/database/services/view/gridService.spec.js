import { reconstructCompactGridRows } from '@baserow/modules/database/services/view/grid'

describe('reconstructCompactGridRows', () => {
  test('reconstructs positional rows from the fields header', () => {
    const data = {
      count: 2,
      fields: ['id', 'order', 'field_1', 'field_2'],
      results: [
        [1, '1.0', 10, [20, 21]],
        [2, '2.0', null, []],
      ],
    }
    reconstructCompactGridRows(data)
    expect(data.fields).toBeUndefined()
    expect(data.count).toBe(2)
    expect(data.results).toStrictEqual([
      { id: 1, order: '1.0', field_1: 10, field_2: [20, 21] },
      { id: 2, order: '2.0', field_1: null, field_2: [] },
    ])
  })

  test('is a no-op for a regular (non-positional) response', () => {
    const data = { results: [{ id: 1, field_1: 10 }] }
    reconstructCompactGridRows(data)
    expect(data.results).toStrictEqual([{ id: 1, field_1: 10 }])
  })

  test('handles an empty positional response', () => {
    const data = { fields: ['id', 'field_1'], results: [] }
    reconstructCompactGridRows(data)
    expect(data.fields).toBeUndefined()
    expect(data.results).toStrictEqual([])
  })
})
