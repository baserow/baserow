import { TestApp } from '@baserow/test/helpers/testApp'
import { rehydrateCompactRows } from '@baserow/modules/database/store/view/grid'

const singleField = {
  id: 1,
  type: 'single_select',
  select_options: [
    { id: 10, value: 'A', color: 'red' },
    { id: 11, value: 'B', color: 'blue' },
  ],
}
const multiField = {
  id: 2,
  type: 'multiple_select',
  select_options: [
    { id: 20, value: 'X', color: 'green' },
    { id: 21, value: 'Y', color: 'yellow' },
  ],
}
const textField = { id: 3, type: 'text' }

describe('grid compact notation rehydration', () => {
  let testApp = null
  let registry = null

  beforeEach(() => {
    testApp = new TestApp()
    registry = testApp.store.$registry
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('single select getRowValueFromCompactValue resolves the id', () => {
    const type = registry.get('field', 'single_select')
    expect(type.getRowValueFromCompactValue(singleField, 10)).toStrictEqual({
      id: 10,
      value: 'A',
      color: 'red',
    })
    expect(type.getRowValueFromCompactValue(singleField, null)).toBe(null)
    // Idempotent: an already resolved value is left untouched.
    const full = { id: 11, value: 'B', color: 'blue' }
    expect(type.getRowValueFromCompactValue(singleField, full)).toStrictEqual(
      full
    )
  })

  test('multiple select getRowValueFromCompactValue resolves the ids in order', () => {
    const type = registry.get('field', 'multiple_select')
    expect(
      type.getRowValueFromCompactValue(multiField, [21, 20])
    ).toStrictEqual([
      { id: 21, value: 'Y', color: 'yellow' },
      { id: 20, value: 'X', color: 'green' },
    ])
    expect(type.getRowValueFromCompactValue(multiField, [])).toStrictEqual([])
    // Idempotent: already resolved options pass through.
    const full = [{ id: 20, value: 'X', color: 'green' }]
    expect(type.getRowValueFromCompactValue(multiField, full)).toStrictEqual(
      full
    )
  })

  test('non compact field types are unchanged', () => {
    const type = registry.get('field', 'text')
    expect(type.isCompactNotationSupported()).toBe(false)
    expect(type.getRowValueFromCompactValue(textField, 'hello')).toBe('hello')
  })

  test('rehydrateCompactRows only rewrites select cells', () => {
    const rows = [
      { id: 1, field_1: 10, field_2: [20, 21], field_3: 'hello' },
      { id: 2, field_1: null, field_2: [], field_3: '' },
    ]
    rehydrateCompactRows(rows, [singleField, multiField, textField], registry)

    expect(rows[0].field_1).toStrictEqual({ id: 10, value: 'A', color: 'red' })
    expect(rows[0].field_2).toStrictEqual([
      { id: 20, value: 'X', color: 'green' },
      { id: 21, value: 'Y', color: 'yellow' },
    ])
    expect(rows[0].field_3).toBe('hello')
    expect(rows[1].field_1).toBe(null)
    expect(rows[1].field_2).toStrictEqual([])

    // Running it again on already rehydrated rows is a no-op.
    const before = JSON.parse(JSON.stringify(rows))
    rehydrateCompactRows(rows, [singleField, multiField, textField], registry)
    expect(JSON.parse(JSON.stringify(rows))).toStrictEqual(before)
  })
})
