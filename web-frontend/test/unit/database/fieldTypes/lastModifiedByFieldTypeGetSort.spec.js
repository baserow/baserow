import { TestApp } from '@baserow/test/helpers/testApp'
import { firstBy } from 'thenby'
import workspaceStore from '@baserow/modules/core/store/workspace'
import { LastModifiedByFieldType } from '@baserow/modules/database/fieldTypes'

const tableRows = [
  {
    id: 1,
    order: '1.00000000000000000000',
    field: { id: 2, name: 'User B' },
  },
  {
    id: 2,
    order: '2.00000000000000000000',
    field: { id: 1, name: 'User A' },
  },
  {
    id: 3,
    order: '3.00000000000000000000',
    field: { id: 3, name: 'User C' },
  },
  {
    id: 4,
    order: '4.00000000000000000000',
    field: { id: 4, name: 'User B' },
  },
  {
    id: 5,
    order: '5.00000000000000000000',
    field: null,
  },
  {
    id: 6,
    order: '6.00000000000000000000',
    field: { id: 5, name: 'Loaded from workspace as User BBB' },
  },
]

describe('LastModifiedByFieldType.getSort()', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()

    const state = Object.assign(workspaceStore.state(), {
      items: [
        {
          users: [
            {
              user_id: 5,
              name: 'User BBB',
            },
          ],
        },
      ],
    })

    store = testApp.createStore({
      modules: { workspace: { ...workspaceStore, state: () => state } },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('sorting based on the provided user name', () => {
    const lastModifiedByField = {}

    const context = { app: { ...useNuxtApp(), $store: store } }

    const lastModifiedByType = new LastModifiedByFieldType(context)

    expect(lastModifiedByType.getCanSortInView(lastModifiedByField)).toBe(true)

    const ASC = lastModifiedByType.getSort('field', 'ASC', lastModifiedByField)
    const sortASC = firstBy().thenBy(ASC)
    const DESC = lastModifiedByType.getSort(
      'field',
      'DESC',
      lastModifiedByField
    )
    const sortDESC = firstBy().thenBy(DESC)

    tableRows.sort(sortASC)

    const sorted = tableRows.map((obj) => obj.field)
    const expected = [
      null,
      { id: 1, name: 'User A' },
      { id: 2, name: 'User B' },
      { id: 4, name: 'User B' },
      { id: 5, name: 'Loaded from workspace as User BBB' },
      { id: 3, name: 'User C' },
    ]

    expect(sorted).toEqual(expected)

    tableRows.sort(sortDESC)

    const sortedReversed = tableRows.map((obj) => obj.field)

    const expectedReversed = [
      { id: 3, name: 'User C' },
      { id: 5, name: 'Loaded from workspace as User BBB' },
      { id: 2, name: 'User B' },
      { id: 4, name: 'User B' },
      { id: 1, name: 'User A' },
      null,
    ]

    expect(sortedReversed).toEqual(expectedReversed)
  })
})
