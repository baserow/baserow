import { TestApp } from '@baserow/test/helpers/testApp'
import { firstBy } from 'thenby'

describe('LinkRowFieldType.getGroupBySort()', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('delegates to getSort via getSortTypes, passing field through', () => {
    const fieldType = testApp._app.$registry.get('field', 'link_row')

    const field = {
      id: 10,
      type: 'link_row',
      link_row_table_primary_field: { id: 1, type: 'text' },
    }

    const rows = [
      {
        id: 1,
        order: '1.00000000000000000000',
        field_10: [{ id: 1, value: 'Banana' }],
      },
      {
        id: 2,
        order: '2.00000000000000000000',
        field_10: [{ id: 2, value: 'Apple' }],
      },
      {
        id: 3,
        order: '3.00000000000000000000',
        field_10: [],
      },
    ]

    const sortFn = fieldType.getGroupBySort('field_10', 'ASC', field, 'default')
    rows.sort(firstBy().thenBy(sortFn))
    expect(rows.map((r) => r.id)).toEqual([3, 2, 1])
  })
})
