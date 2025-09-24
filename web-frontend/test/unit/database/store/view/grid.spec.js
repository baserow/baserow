import gridStore from '@baserow/modules/database/store/view/grid'
import { TestApp } from '@baserow/test/helpers/testApp'
import {
  EqualViewFilterType,
  ContainsViewFilterType,
} from '@baserow/modules/database/viewFilters'
import { clone } from '@baserow/modules/core/utils/object'

describe('Grid view store', () => {
  let testApp = null
  let store = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('visibleByScrollTop', async () => {
    const state = Object.assign(gridStore.state(), {
      rowPadding: 1,
      bufferStartIndex: 0,
      bufferLimit: 9,
      bufferRequestSize: 3,
      rows: [
        { id: 1, order: '1.00' },
        { id: 2, order: '2.00' },
        { id: 3, order: '3.00' },
        { id: 4, order: '4.00' },
        { id: 5, order: '5.00' },
        { id: 6, order: '6.00' },
        { id: 7, order: '7.00' },
        { id: 8, order: '8.00' },
        { id: 9, order: '9.00' },
      ],
      count: 100,
      windowHeight: 99,
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    await store.dispatch('grid/visibleByScrollTop', 0)
    expect(store.getters['grid/getRowsTop']).toBe(0)
    expect(store.getters['grid/getRowsStartIndex']).toBe(0)
    expect(store.getters['grid/getRowsEndIndex']).toBe(3)

    await store.dispatch('grid/visibleByScrollTop', 10)
    expect(store.getters['grid/getRowsTop']).toBe(0)
    expect(store.getters['grid/getRowsStartIndex']).toBe(0)
    expect(store.getters['grid/getRowsEndIndex']).toBe(3)

    await store.dispatch('grid/visibleByScrollTop', 33)
    expect(store.getters['grid/getRowsTop']).toBe(33)
    expect(store.getters['grid/getRowsStartIndex']).toBe(1)
    expect(store.getters['grid/getRowsEndIndex']).toBe(4)

    await store.dispatch('grid/visibleByScrollTop', 66)
    expect(store.getters['grid/getRowsTop']).toBe(66)
    expect(store.getters['grid/getRowsStartIndex']).toBe(2)
    expect(store.getters['grid/getRowsEndIndex']).toBe(5)

    await store.dispatch('grid/visibleByScrollTop', 396)
    expect(store.getters['grid/getRowsTop']).toBe(297)
    expect(store.getters['grid/getRowsStartIndex']).toBe(9)
    expect(store.getters['grid/getRowsEndIndex']).toBe(9)

    store.state.grid.bufferStartIndex = 9
    store.state.grid.rows = [
      { id: 10, order: '10.00' },
      { id: 11, order: '11.00' },
      { id: 12, order: '12.00' },
      { id: 13, order: '13.00' },
      { id: 14, order: '14.00' },
      { id: 15, order: '15.00' },
      { id: 16, order: '16.00' },
      { id: 17, order: '17.00' },
      { id: 18, order: '18.00' },
    ]

    await store.dispatch('grid/visibleByScrollTop', 396)
    expect(store.getters['grid/getRowsTop']).toBe(396)
    expect(store.getters['grid/getRowsStartIndex']).toBe(3)
    expect(store.getters['grid/getRowsEndIndex']).toBe(6)
  })

  test('createdNewRow', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 6,
      rows: [
        { id: 2, order: '2.00000000000000000000' },
        { id: 3, order: '3.00000000000000000000' },
        { id: 4, order: '4.00000000000000000000' },
        { id: 5, order: '5.00000000000000000000' },
        { id: 6, order: '6.00000000000000000000' },
        { id: 7, order: '7.00000000000000000000' },
      ],
      count: 100,
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      filters: [],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = []
    const getScrollTop = () => 0

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: { id: 1, order: '1.00000000000000000000' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(7)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(7)
    expect(store.getters['grid/getCount']).toBe(101)

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: { id: 8, order: '4.50000000000000000000' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(8)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][4].id).toBe(8)
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(8)
    expect(store.getters['grid/getCount']).toBe(102)

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: { id: 102, order: '102.00000000000000000000' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(8)
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(8)
    expect(store.getters['grid/getCount']).toBe(103)

    store.state.grid.bufferStartIndex = 9
    store.state.grid.bufferLimit = 6
    store.state.grid.rows = [
      { id: 10, order: '10.00000000000000000000' },
      { id: 11, order: '11.00000000000000000000' },
      { id: 12, order: '12.00000000000000000000' },
      { id: 13, order: '13.00000000000000000000' },
      { id: 14, order: '14.00000000000000000000' },
      { id: 15, order: '15.00000000000000000000' },
    ]

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: { id: 2, order: '2.00000000000000000000' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(6)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getBufferStartIndex']).toBe(10)
    expect(store.getters['grid/getBufferLimit']).toBe(6)
    expect(store.getters['grid/getCount']).toBe(104)

    // When creating a new row that does not match the filters we don't expect
    // anything to happen because the row does not belong on that view.
    await store.dispatch('grid/createdNewRow', {
      view: {
        id: 1,
        filters_disabled: false,
        filter_type: 'AND',
        filters: [
          {
            id: 1,
            view: 1,
            field: 1,
            type: EqualViewFilterType.getType(),
            value: 'not_matching',
          },
        ],
        sortings: [],
        ownership_type: 'collaborative',
      },
      fields: [
        {
          id: 1,
          name: 'Test 1',
          type: 'text',
          primary: true,
        },
      ],
      values: { id: 16, order: '11.50000000000000000000', field_1: 'value' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(6)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getAllRows'][1].id).toBe(11)
    expect(store.getters['grid/getAllRows'][2].id).toBe(12)
    expect(store.getters['grid/getAllRows'][3].id).toBe(13)
    expect(store.getters['grid/getAllRows'][4].id).toBe(14)
    expect(store.getters['grid/getAllRows'][5].id).toBe(15)
    expect(store.getters['grid/getBufferStartIndex']).toBe(10)
    expect(store.getters['grid/getBufferLimit']).toBe(6)
    expect(store.getters['grid/getCount']).toBe(104)
  })

  test('updatedExistingRow', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 3,
      rows: [
        { id: 1, order: '1.00000000000000000000', field_1: 'Value 1' },
        {
          id: 2,
          order: '2.00000000000000000000',
          field_1: 'Value 2',
          _: { mustPersist: true },
        },
        { id: 3, order: '3.00000000000000000000', field_1: 'Value 3' },
      ],
      count: 3,
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      id: 1,
      filters_disabled: false,
      filter_type: 'AND',
      filters: [
        {
          id: 1,
          view: 1,
          field: 1,
          type: ContainsViewFilterType.getType(),
          value: 'value',
        },
      ],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = [
      {
        id: 1,
        name: 'Test 1',
        type: 'text',
        primary: true,
      },
    ]
    const getScrollTop = () => 0

    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 2, order: '2.00000000000000000000', field_1: 'Value 2' },
      values: { field_1: 'Value 2 updated' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(3)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 1')
    expect(store.getters['grid/getAllRows'][1].id).toBe(2)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 2 updated')
    expect(store.getters['grid/getAllRows'][1]._.mustPersist).toBe(true)
    expect(store.getters['grid/getAllRows'][2].id).toBe(3)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 3')
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(3)
    expect(store.getters['grid/getCount']).toBe(3)

    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 1, order: '1.00000000000000000000', field_1: 'Value 1' },
      values: { field_1: 'Value 1 updated' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(3)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 1 updated')
    expect(store.getters['grid/getAllRows'][1].id).toBe(2)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 2 updated')
    expect(store.getters['grid/getAllRows'][2].id).toBe(3)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 3')
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(3)
    expect(store.getters['grid/getCount']).toBe(3)

    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 3, order: '3.00000000000000000000', field_1: 'Value 3' },
      values: { field_1: 'Value 3 updated' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(3)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 1 updated')
    expect(store.getters['grid/getAllRows'][1].id).toBe(2)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 2 updated')
    expect(store.getters['grid/getAllRows'][2].id).toBe(3)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 3 updated')
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(3)
    expect(store.getters['grid/getCount']).toBe(3)

    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 4, order: '4.00000000000000000000', field_1: 'empty' },
      values: { field_1: 'Value 4 updated' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(4)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 1 updated')
    expect(store.getters['grid/getAllRows'][1].id).toBe(2)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 2 updated')
    expect(store.getters['grid/getAllRows'][2].id).toBe(3)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 3 updated')
    expect(store.getters['grid/getAllRows'][3].id).toBe(4)
    expect(store.getters['grid/getAllRows'][3].field_1).toBe('Value 4 updated')
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(4)
    expect(store.getters['grid/getCount']).toBe(4)

    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Value 4 updated',
      },
      values: { field_1: 'empty' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(3)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 1 updated')
    expect(store.getters['grid/getAllRows'][1].id).toBe(2)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 2 updated')
    expect(store.getters['grid/getAllRows'][2].id).toBe(3)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 3 updated')
    expect(store.getters['grid/getBufferStartIndex']).toBe(0)
    expect(store.getters['grid/getBufferLimit']).toBe(3)
    expect(store.getters['grid/getCount']).toBe(3)

    store.state.grid.bufferStartIndex = 9
    store.state.grid.bufferLimit = 6
    store.state.grid.rows = [
      { id: 10, order: '10.00000000000000000000', field_1: 'Value 10' },
      { id: 11, order: '11.00000000000000000000', field_1: 'Value 11' },
      { id: 12, order: '12.00000000000000000000', field_1: 'Value 12' },
      { id: 13, order: '13.00000000000000000000', field_1: 'Value 13' },
      { id: 14, order: '14.00000000000000000000', field_1: 'Value 14' },
      { id: 15, order: '15.00000000000000000000', field_1: 'Value 15' },
    ]
    store.state.grid.count = 100

    // Change the first row in the buffer. We expect it to be removed from the
    // buffer because aren't 100% sure it still belongs in the buffer.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 10, order: '10.00000000000000000000', field_1: 'Value 10' },
      values: { field_1: 'Value 10 updated' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(5)
    expect(store.getters['grid/getAllRows'][0].id).toBe(11)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 11')
    expect(store.getters['grid/getAllRows'][1].id).toBe(12)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 12')
    expect(store.getters['grid/getAllRows'][2].id).toBe(13)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 13')
    expect(store.getters['grid/getAllRows'][3].id).toBe(14)
    expect(store.getters['grid/getAllRows'][3].field_1).toBe('Value 14')
    expect(store.getters['grid/getAllRows'][4].id).toBe(15)
    expect(store.getters['grid/getAllRows'][4].field_1).toBe('Value 15')
    expect(store.getters['grid/getBufferStartIndex']).toBe(10)
    expect(store.getters['grid/getBufferLimit']).toBe(5)
    expect(store.getters['grid/getCount']).toBe(100)

    // Change the last row in the buffer. We expect it to be deleted from the buffer
    // because it we aren't 100% sure it still belongs in the buffer.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 15, order: '15.00000000000000000000', field_1: 'Value 15' },
      values: { field_1: 'Value 15 updated' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(4)
    expect(store.getters['grid/getAllRows'][0].id).toBe(11)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 11')
    expect(store.getters['grid/getAllRows'][1].id).toBe(12)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 12')
    expect(store.getters['grid/getAllRows'][2].id).toBe(13)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 13')
    expect(store.getters['grid/getAllRows'][3].id).toBe(14)
    expect(store.getters['grid/getAllRows'][3].field_1).toBe('Value 14')
    expect(store.getters['grid/getBufferStartIndex']).toBe(10)
    expect(store.getters['grid/getBufferLimit']).toBe(4)
    expect(store.getters['grid/getCount']).toBe(100)

    // Move a row in the buffer to another position in the buffer.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 12, order: '12.00000000000000000000', field_1: 'Value 12' },
      values: {
        order: '13.50000000000000000000',
        field_1: 'Value 13.5',
      },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(4)
    expect(store.getters['grid/getAllRows'][0].id).toBe(11)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 11')
    expect(store.getters['grid/getAllRows'][1].id).toBe(13)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 13')
    expect(store.getters['grid/getAllRows'][2].id).toBe(12)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 13.5')
    expect(store.getters['grid/getAllRows'][3].id).toBe(14)
    expect(store.getters['grid/getAllRows'][3].field_1).toBe('Value 14')
    expect(store.getters['grid/getBufferStartIndex']).toBe(10)
    expect(store.getters['grid/getBufferLimit']).toBe(4)
    expect(store.getters['grid/getCount']).toBe(100)

    // Move an existing row before the buffer. We expect the row to be removed from
    // the buffer because we can't be 100% sure it still belongs in there.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 12,
        order: '13.50000000000000000000',
        field_1: 'Value 13.5',
      },
      values: {
        order: '2.99999999999999999999',
      },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(3)
    expect(store.getters['grid/getAllRows'][0].id).toBe(11)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 11')
    expect(store.getters['grid/getAllRows'][1].id).toBe(13)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 13')
    expect(store.getters['grid/getAllRows'][2].id).toBe(14)
    expect(store.getters['grid/getAllRows'][2].field_1).toBe('Value 14')
    expect(store.getters['grid/getBufferStartIndex']).toBe(11)
    expect(store.getters['grid/getBufferLimit']).toBe(3)
    expect(store.getters['grid/getCount']).toBe(100)

    // Move an existing row before the buffer. We expect the row to be removed from
    // the buffer because we can't be 100% sure it still belongs in there.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 13,
        order: '13.00000000000000000000',
        field_1: 'Value 13',
      },
      values: {
        order: '16.99999999999999999999',
      },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(2)
    expect(store.getters['grid/getAllRows'][0].id).toBe(11)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 11')
    expect(store.getters['grid/getAllRows'][1].id).toBe(14)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 14')
    expect(store.getters['grid/getBufferStartIndex']).toBe(11)
    expect(store.getters['grid/getBufferLimit']).toBe(2)
    expect(store.getters['grid/getCount']).toBe(100)

    // Move a row that is not in the buffer from before to after.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 2,
        order: '2.00000000000000000000',
        field_1: 'Value 2',
      },
      values: {
        order: '20.99999999999999999999',
        field_2: 'Value 20',
      },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(2)
    expect(store.getters['grid/getAllRows'][0].id).toBe(11)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 11')
    expect(store.getters['grid/getAllRows'][1].id).toBe(14)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 14')
    expect(store.getters['grid/getBufferStartIndex']).toBe(10)
    expect(store.getters['grid/getBufferLimit']).toBe(2)
    expect(store.getters['grid/getCount']).toBe(100)

    // Move a row that is not in the buffer from before to after.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 2,
        order: '20.99999999999999999999',
        field_1: 'Value 20',
      },
      values: {
        order: '2.99999999999999999999',
        field_2: 'Value 20',
      },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(2)
    expect(store.getters['grid/getAllRows'][0].id).toBe(11)
    expect(store.getters['grid/getAllRows'][0].field_1).toBe('Value 11')
    expect(store.getters['grid/getAllRows'][1].id).toBe(14)
    expect(store.getters['grid/getAllRows'][1].field_1).toBe('Value 14')
    expect(store.getters['grid/getBufferStartIndex']).toBe(11)
    expect(store.getters['grid/getBufferLimit']).toBe(2)
    expect(store.getters['grid/getCount']).toBe(100)

    store.state.grid.bufferStartIndex = 9
    store.state.grid.bufferLimit = 6
    store.state.grid.rows = [
      { id: 10, order: '14.99999999999999999995', field_1: 'Value 10' },
      { id: 11, order: '14.99999999999999999996', field_1: 'Value 11' },
      { id: 12, order: '14.99999999999999999997', field_1: 'Value 12' },
      { id: 13, order: '14.99999999999999999998', field_1: 'Value 13' },
      { id: 14, order: '14.99999999999999999999', field_1: 'Value 14' },
      { id: 15, order: '15.00000000000000000000', field_1: 'Value 15' },
    ]
    store.state.grid.count = 100

    // Move the row to an order that already exists, which means all the order lower
    // than the new order should be decreased by 0.00000000000000000001.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 11,
        order: '14.99999999999999999996',
        field_1: 'Value 11',
      },
      values: {
        order: '14.99999999999999999999',
      },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(6)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getAllRows'][0].order).toBe(
      '14.99999999999999999994'
    )
    expect(store.getters['grid/getAllRows'][1].id).toBe(12)
    expect(store.getters['grid/getAllRows'][1].order).toBe(
      '14.99999999999999999996'
    )
    expect(store.getters['grid/getAllRows'][2].id).toBe(13)
    expect(store.getters['grid/getAllRows'][2].order).toBe(
      '14.99999999999999999997'
    )
    expect(store.getters['grid/getAllRows'][3].id).toBe(14)
    expect(store.getters['grid/getAllRows'][3].order).toBe(
      '14.99999999999999999998'
    )
    expect(store.getters['grid/getAllRows'][4].id).toBe(11)
    expect(store.getters['grid/getAllRows'][4].order).toBe(
      '14.99999999999999999999'
    )
    expect(store.getters['grid/getAllRows'][5].id).toBe(15)
    expect(store.getters['grid/getAllRows'][5].order).toBe(
      '15.00000000000000000000'
    )
    expect(store.getters['grid/getBufferStartIndex']).toBe(9)
    expect(store.getters['grid/getBufferLimit']).toBe(6)
    expect(store.getters['grid/getCount']).toBe(100)

    // If only a field value is updated then there the other row order don't have to be
    // decreased.
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 11,
        order: '14.99999999999999999999',
        field_1: 'Value 11',
      },
      values: {
        field_1: 'Value 11.1',
      },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(6)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getAllRows'][0].order).toBe(
      '14.99999999999999999994'
    )
    expect(store.getters['grid/getAllRows'][1].id).toBe(12)
    expect(store.getters['grid/getAllRows'][1].order).toBe(
      '14.99999999999999999996'
    )
    expect(store.getters['grid/getAllRows'][2].id).toBe(13)
    expect(store.getters['grid/getAllRows'][2].order).toBe(
      '14.99999999999999999997'
    )
    expect(store.getters['grid/getAllRows'][3].id).toBe(14)
    expect(store.getters['grid/getAllRows'][3].order).toBe(
      '14.99999999999999999998'
    )
    expect(store.getters['grid/getAllRows'][4].id).toBe(11)
    expect(store.getters['grid/getAllRows'][4].order).toBe(
      '14.99999999999999999999'
    )
    expect(store.getters['grid/getAllRows'][5].id).toBe(15)
    expect(store.getters['grid/getAllRows'][5].order).toBe(
      '15.00000000000000000000'
    )
    expect(store.getters['grid/getBufferStartIndex']).toBe(9)
    expect(store.getters['grid/getBufferLimit']).toBe(6)
    expect(store.getters['grid/getCount']).toBe(100)
  })

  test('deletedExistingRow', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 9,
      bufferLimit: 6,
      rows: [
        { id: 10, order: '10.00000000000000000000' },
        { id: 11, order: '11.00000000000000000000' },
        { id: 12, order: '12.00000000000000000000' },
        { id: 13, order: '13.00000000000000000000' },
        { id: 14, order: '14.00000000000000000000' },
        { id: 15, order: '15.00000000000000000000' },
      ],
      count: 100,
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      filters: [],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = []
    const getScrollTop = () => 0

    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: { id: 3, order: '3.00000000000000000000' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(6)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getAllRows'][1].id).toBe(11)
    expect(store.getters['grid/getAllRows'][2].id).toBe(12)
    expect(store.getters['grid/getAllRows'][3].id).toBe(13)
    expect(store.getters['grid/getAllRows'][4].id).toBe(14)
    expect(store.getters['grid/getAllRows'][5].id).toBe(15)
    expect(store.getters['grid/getBufferStartIndex']).toBe(8)
    expect(store.getters['grid/getBufferLimit']).toBe(6)
    expect(store.getters['grid/getCount']).toBe(99)

    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: { id: 20, order: '20.00000000000000000000' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(6)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getAllRows'][1].id).toBe(11)
    expect(store.getters['grid/getAllRows'][2].id).toBe(12)
    expect(store.getters['grid/getAllRows'][3].id).toBe(13)
    expect(store.getters['grid/getAllRows'][4].id).toBe(14)
    expect(store.getters['grid/getAllRows'][5].id).toBe(15)
    expect(store.getters['grid/getBufferStartIndex']).toBe(8)
    expect(store.getters['grid/getBufferLimit']).toBe(6)
    expect(store.getters['grid/getCount']).toBe(98)

    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: { id: 13, order: '13.00000000000000000000' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(5)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getAllRows'][1].id).toBe(11)
    expect(store.getters['grid/getAllRows'][2].id).toBe(12)
    expect(store.getters['grid/getAllRows'][3].id).toBe(14)
    expect(store.getters['grid/getAllRows'][4].id).toBe(15)
    expect(store.getters['grid/getBufferStartIndex']).toBe(8)
    expect(store.getters['grid/getBufferLimit']).toBe(5)
    expect(store.getters['grid/getCount']).toBe(97)

    // When deleting a new row that does not match the filters we don't expect
    // anything to happen because the row does not belong on that view.
    await store.dispatch('grid/deletedExistingRow', {
      view: {
        id: 1,
        filters_disabled: false,
        filter_type: 'AND',
        filters: [
          {
            id: 1,
            view: 1,
            field: 1,
            type: EqualViewFilterType.getType(),
            value: 'not_matching',
          },
        ],
        sortings: [],
        ownership_type: 'collaborative',
      },
      fields: [
        {
          id: 1,
          name: 'Test 1',
          type: 'text',
          primary: true,
        },
      ],
      row: { id: 16, order: '11.50000000000000000000', field_1: 'value' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(5)
    expect(store.getters['grid/getAllRows'][0].id).toBe(10)
    expect(store.getters['grid/getAllRows'][1].id).toBe(11)
    expect(store.getters['grid/getAllRows'][2].id).toBe(12)
    expect(store.getters['grid/getAllRows'][3].id).toBe(14)
    expect(store.getters['grid/getAllRows'][4].id).toBe(15)
    expect(store.getters['grid/getBufferStartIndex']).toBe(8)
    expect(store.getters['grid/getBufferLimit']).toBe(5)
    expect(store.getters['grid/getCount']).toBe(97)
  })
  test('row metadata stored when provided on row create or update', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 6,
      rows: [{ id: 2, order: '2.00000000000000000000' }],
      count: 1,
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      id: 1,
      filters: [],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = []
    const getScrollTop = () => 0

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: { id: 1, order: '1.00000000000000000000' },
      metadata: { test: 'test' },
      getScrollTop,
    })
    expect(store.getters['grid/getAllRows'].length).toBe(2)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][0]._.metadata.test).toBe('test')

    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: { id: 1, order: '1.00000000000000000000' },
      values: { field_1: 'Value updated' },
      metadata: { test: 'test updated' },
      getScrollTop,
    })

    expect(store.getters['grid/getAllRows'].length).toBe(2)
    expect(store.getters['grid/getAllRows'][0].id).toBe(1)
    expect(store.getters['grid/getAllRows'][0]._.metadata.test).toBe(
      'test updated'
    )
  })

  test('fetchAllFieldAggregationData', async () => {
    const state = Object.assign(gridStore.state(), {
      fieldAggregationData: {},
      fieldOptions: {
        2: { aggregation_raw_type: 'empty_count' },
        3: { aggregation_raw_type: 'not_empty_count' },
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      id: 1,
    }

    mockServer.getAllFieldAggregationData(view.id, {
      field_2: 84,
      field_3: 256,
    })

    await store.dispatch('grid/fetchAllFieldAggregationData', {
      view,
    })

    expect(clone(store.getters['grid/getAllFieldAggregationData'])).toEqual({
      2: {
        loading: false,
        value: 84,
      },
      3: {
        loading: false,
        value: 256,
      },
    })

    // What if the query fails?
    mockServer.getAllFieldAggregationData(view.id, null, true)

    testApp.dontFailOnErrorResponses()
    await expect(
      store.dispatch('grid/fetchAllFieldAggregationData', {
        view,
      })
    ).rejects.toThrowErrorMatchingSnapshot()
    testApp.failOnErrorResponses()

    expect(clone(store.getters['grid/getAllFieldAggregationData'])).toEqual({
      2: {
        loading: false,
        value: null,
      },
      3: {
        loading: false,
        value: null,
      },
    })
  })

  test('getNumberOfVisibleFields', () => {
    const state = Object.assign(gridStore.state(), {
      fieldOptions: {
        1: {
          order: 0,
          hidden: false,
        },
        2: {
          order: 1,
          hidden: true,
        },
        3: {
          order: 3,
          hidden: false,
        },
        4: {
          order: 2,
          hidden: false,
        },
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    expect(store.getters['grid/getNumberOfVisibleFields']).toBe(3)
  })

  test('getOrderedFieldOptions', () => {
    const fields = []
    const state = Object.assign(gridStore.state(), {
      fieldOptions: {
        1: {
          order: 0,
          hidden: false,
        },
        2: {
          order: 1,
          hidden: true,
        },
        3: {
          order: 3,
          hidden: false,
        },
        4: {
          order: 2,
          hidden: false,
        },
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    expect(
      JSON.parse(
        JSON.stringify(store.getters['grid/getOrderedFieldOptions'](fields))
      )
    ).toEqual([
      [1, { hidden: false, order: 0 }],
      [2, { hidden: true, order: 1 }],
      [4, { hidden: false, order: 2 }],
      [3, { hidden: false, order: 3 }],
    ])
  })

  test('getOrderedFieldOptions places primary field first', () => {
    const fields = [
      { id: 2, primary: false },
      { id: 3, primary: true },
    ]
    const state = Object.assign(gridStore.state(), {
      fieldOptions: {
        1: {
          order: 0,
          hidden: false,
        },
        2: {
          order: 1,
          hidden: true,
        },
        3: {
          order: 3,
          hidden: false,
        },
        4: {
          order: 2,
          hidden: false,
        },
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    expect(
      JSON.parse(
        JSON.stringify(store.getters['grid/getOrderedFieldOptions'](fields))
      )
    ).toEqual([
      [3, { hidden: false, order: 3 }],
      [1, { hidden: false, order: 0 }],
      [2, { hidden: true, order: 1 }],
      [4, { hidden: false, order: 2 }],
    ])
  })

  test('getOrderedVisibleFieldOptions', () => {
    const fields = []
    const state = Object.assign(gridStore.state(), {
      fieldOptions: {
        1: {
          order: 0,
          hidden: false,
        },
        2: {
          order: 1,
          hidden: true,
        },
        3: {
          order: 3,
          hidden: false,
        },
        4: {
          order: 2,
          hidden: false,
        },
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    expect(
      JSON.parse(
        JSON.stringify(
          store.getters['grid/getOrderedVisibleFieldOptions'](fields)
        )
      )
    ).toEqual([
      [1, { hidden: false, order: 0 }],
      [4, { hidden: false, order: 2 }],
      [3, { hidden: false, order: 3 }],
    ])
  })

  test('getRowIdByIndex', () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 9,
      bufferLimit: 10,

      rows: [
        {
          id: 10,
          field_1: '10',
          field_2: 10,
          field_3: true,
          field_4: 'abc',
          order: '10.00',
          _: {},
        },
        {
          id: 11,
          field_1: '11',
          field_2: 11,
          field_3: true,
          field_4: 'def',
          order: '11.00',
          _: {},
        },
      ],
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    expect(store.getters['grid/getRowIdByIndex'](10)).toBe(11)
  })

  test('getFieldIdByIndex', () => {
    const fields = []
    const state = Object.assign(gridStore.state(), {
      fieldOptions: {
        1: {
          order: 0,
          hidden: false,
        },
        2: {
          order: 1,
          hidden: true,
        },
        3: {
          order: 3,
          hidden: false,
        },
        4: {
          order: 2,
          hidden: false,
        },
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    expect(store.getters['grid/getFieldIdByIndex'](2, fields)).toBe(3)
  })

  test('UPDATE_GROUP_BY_METADATA mutation', () => {
    const state = Object.assign(gridStore.state(), {})
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    store.commit('grid/SET_GROUP_BY_METADATA', {
      field_1: [
        {
          field_1: 1,
          count: 2,
        },
        {
          field_1: 2,
          count: 2,
        },
      ],
      field_2: [
        {
          field_1: 1,
          field_2: 'a',
          count: 1,
        },
        {
          field_1: 1,
          field_2: 'b',
          count: 1,
        },
        {
          field_1: 2,
          field_2: 'a',
          count: 1,
        },
        {
          field_1: 2,
          field_2: 'b',
          count: 1,
        },
      ],
    })

    store.commit('grid/UPDATE_GROUP_BY_METADATA', {
      field_1: [
        {
          count: 4,
          field_1: 1,
        },
        {
          count: 1,
          field_1: 3,
        },
      ],
      field_2: [
        {
          count: 2,
          field_1: 1,
          field_2: 'a',
        },
        {
          count: 1,
          field_1: 1,
          field_2: 'c',
        },
        {
          count: 1,
          field_1: 3,
          field_2: 'a',
        },
      ],
    })

    expect(store.state.grid.groupByMetadata).toEqual({
      field_1: [
        {
          count: 4,
          field_1: 1,
        },
        {
          count: 2,
          field_1: 2,
        },
        {
          count: 1,
          field_1: 3,
        },
      ],
      field_2: [
        {
          count: 2,
          field_1: 1,
          field_2: 'a',
        },
        {
          count: 1,
          field_1: 1,
          field_2: 'b',
        },
        {
          count: 1,
          field_1: 2,
          field_2: 'a',
        },
        {
          count: 1,
          field_1: 2,
          field_2: 'b',
        },
        {
          count: 1,
          field_1: 1,
          field_2: 'c',
        },
        {
          count: 1,
          field_1: 3,
          field_2: 'a',
        },
      ],
    })
  })

  test('group by metadata count increase on row create', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 0,
      rows: [],
      count: 100,
      activeGroupBys: [
        {
          id: 1,
          field: 1,
          order: 'ASC',
        },
        {
          id: 2,
          field: 2,
          order: 'ASC',
        },
      ],
      groupByMetadata: {
        field_1: [
          {
            field_1: 'a',
            count: 1,
          },
          {
            field_1: 'b',
            count: 1,
          },
        ],
        field_2: [
          {
            field_1: 'a',
            field_2: 1,
            count: 1,
          },
          {
            field_1: 'b',
            field_2: 1,
            count: 1,
          },
        ],
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      id: 1,
      filters_disabled: false,
      filter_type: 'AND',
      filters: [],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = [
      {
        id: 1,
        name: 'Test 1',
        type: 'text',
        primary: true,
      },
      {
        id: 2,
        name: 'Test 1',
        type: 'number',
        primary: false,
      },
    ]
    const getScrollTop = () => 0

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'a',
        field_2: 1,
      },
      getScrollTop,
    })
    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: {
        id: 2,
        order: '2.00000000000000000000',
        field_1: 'b',
        field_2: 2,
      },
      getScrollTop,
    })
    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'c',
        field_2: 1,
      },
      getScrollTop,
    })
    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'c',
        field_2: 2,
      },
      getScrollTop,
    })

    expect(store.state.grid.groupByMetadata).toEqual({
      field_1: [
        {
          field_1: 'a',
          count: 2,
        },
        {
          field_1: 'b',
          count: 2,
        },
        {
          count: 2,
          field_1: 'c',
        },
      ],
      field_2: [
        {
          field_1: 'a',
          field_2: 1,
          count: 2,
        },
        {
          field_1: 'b',
          field_2: 1,
          count: 1,
        },
        {
          count: 1,
          field_1: 'b',
          field_2: 2,
        },
        {
          count: 1,
          field_1: 'c',
          field_2: 1,
        },
        {
          count: 1,
          field_1: 'c',
          field_2: 2,
        },
      ],
    })
  })

  test('group by metadata count decrease on row delete', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 0,
      rows: [],
      count: 100,
      activeGroupBys: [
        {
          id: 1,
          field: 1,
          order: 'ASC',
        },
        {
          id: 2,
          field: 2,
          order: 'ASC',
        },
      ],
      groupByMetadata: {
        field_1: [
          {
            field_1: 'a',
            count: 2,
          },
          {
            field_1: 'b',
            count: 2,
          },
        ],
        field_2: [
          {
            field_1: 'a',
            field_2: 1,
            count: 1,
          },
          {
            field_1: 'a',
            field_2: 2,
            count: 1,
          },
          {
            field_1: 'b',
            field_2: 1,
            count: 2,
          },
        ],
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      id: 1,
      filters_disabled: false,
      filter_type: 'AND',
      filters: [],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = [
      {
        id: 1,
        name: 'Test 1',
        type: 'text',
        primary: true,
      },
      {
        id: 2,
        name: 'Test 1',
        type: 'number',
        primary: false,
      },
    ]
    const getScrollTop = () => 0

    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'a',
        field_2: 1,
      },
      getScrollTop,
    })
    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'b',
        field_2: 1,
      },
      getScrollTop,
    })
    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'c',
        field_2: 1,
      },
      getScrollTop,
    })

    expect(store.state.grid.groupByMetadata).toEqual({
      field_1: [
        {
          field_1: 'a',
          count: 1,
        },
        {
          field_1: 'b',
          count: 1,
        },
      ],
      field_2: [
        {
          field_1: 'a',
          field_2: 1,
          count: 0,
        },
        {
          field_1: 'a',
          field_2: 2,
          count: 1,
        },
        {
          field_1: 'b',
          field_2: 1,
          count: 1,
        },
      ],
    })
  })

  test('group by metadata count change on row update', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 0,
      rows: [],
      count: 100,
      activeGroupBys: [
        {
          id: 1,
          field: 1,
          order: 'ASC',
        },
        {
          id: 2,
          field: 2,
          order: 'ASC',
        },
      ],
      groupByMetadata: {
        field_1: [
          {
            field_1: 'a',
            count: 1,
          },
          {
            field_1: 'b',
            count: 1,
          },
        ],
        field_2: [
          {
            field_1: 'a',
            field_2: 1,
            count: 1,
          },
          {
            field_1: 'b',
            field_2: 1,
            count: 1,
          },
        ],
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      id: 1,
      filters_disabled: false,
      filter_type: 'AND',
      filters: [],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = [
      {
        id: 1,
        name: 'Test 1',
        type: 'text',
        primary: true,
      },
      {
        id: 2,
        name: 'Test 1',
        type: 'number',
        primary: false,
      },
    ]
    const getScrollTop = () => 0

    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'a',
        field_2: 1,
      },
      values: {
        field_1: 'b',
        field_2: 1,
      },
      getScrollTop,
    })
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 2,
        order: '2.00000000000000000000',
        field_1: 'c',
        field_2: 1,
      },
      values: {
        field_1: 'd',
        field_2: 2,
      },
      getScrollTop,
    })
    await store.dispatch('grid/updatedExistingRow', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'b',
        field_2: 1,
      },
      values: {
        field_1: 'b',
        field_2: 2,
      },
      getScrollTop,
    })

    expect(store.state.grid.groupByMetadata).toEqual({
      field_1: [
        {
          field_1: 'a',
          count: 0,
        },
        {
          field_1: 'b',
          count: 2,
        },
        {
          count: 1,
          field_1: 'd',
        },
      ],
      field_2: [
        {
          field_1: 'a',
          field_2: 1,
          count: 0,
        },
        {
          field_1: 'b',
          field_2: 1,
          count: 1,
        },
        {
          count: 1,
          field_1: 'd',
          field_2: 2,
        },
        {
          count: 1,
          field_1: 'b',
          field_2: 2,
        },
      ],
    })
  })

  test('group by metadata count increase decrease using correct field type methods', async () => {
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 0,
      rows: [],
      count: 100,
      activeGroupBys: [
        {
          id: 1,
          field: 1,
          order: 'ASC',
        },
      ],
      groupByMetadata: {
        field_1: [
          {
            field_1: null,
            count: 0,
          },
          {
            field_1: 1,
            count: 0,
          },
        ],
      },
    })
    gridStore.state = () => state
    store.registerModule('grid', gridStore)

    const view = {
      id: 1,
      filters_disabled: false,
      filter_type: 'AND',
      filters: [],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = [
      {
        id: 1,
        name: 'single_select',
        order: 1,
        primary: false,
        table_id: 0,
        type: 'single_select',
        select_options: [
          {
            id: 1,
            value: 'Test 1',
            color: 'orange',
          },
        ],
      },
    ]
    const getScrollTop = () => 0

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: {
          id: 1,
          value: 'Test 1',
          color: 'orange',
        },
      },
      getScrollTop,
    })
    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: {
        id: 2,
        order: '2.00000000000000000000',
        field_1: null,
      },
      getScrollTop,
    })

    expect(store.state.grid.groupByMetadata).toEqual({
      field_1: [
        {
          field_1: null,
          count: 1,
        },
        {
          field_1: 1,
          count: 1,
        },
      ],
    })

    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: {
        id: 2,
        order: '2.00000000000000000000',
        field_1: null,
      },
      getScrollTop,
    })

    expect(store.state.grid.groupByMetadata).toEqual({
      field_1: [
        {
          field_1: null,
          count: 0,
        },
        {
          field_1: 1,
          count: 1,
        },
      ],
    })
  })
})
