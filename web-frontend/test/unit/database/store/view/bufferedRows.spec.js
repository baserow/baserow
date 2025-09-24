import bufferedRows from '@baserow/modules/database/store/view/bufferedRows'
import { TestApp } from '@baserow/test/helpers/testApp'
import { ContainsViewFilterType } from '@baserow/modules/database/viewFilters'
import { createPrimaryField } from '@baserow/test/fixtures/fields'
import { createView } from '@baserow/test/fixtures/view'

describe('Buffered rows view store helper', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('fetchMissingRowsInNewRange', async () => {
    // A test client that has 100 rows from id 1 through 100. It returns the
    // requested rows they are available.
    const service = () => {
      return {
        fetchRows({ viewId, limit = 100, offset = null }) {
          const all = Array(14)
            .fill(null)
            .map((row, index) => {
              return { id: index + 1 }
            })

          const data = {
            results: all.slice(offset, offset + limit),
          }
          return { data }
        },
      }
    }
    const populateRow = (row) => {
      row._ = {}
      return row
    }
    const testStore = bufferedRows({ service, populateRow })

    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        { id: 1 },
        { id: 2 },
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/fetchMissingRowsInNewRange', {
      startIndex: 0,
      endIndex: 1,
    })
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2]).toBe(null)
    expect(rowsInStore[3]).toBe(null)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9]).toBe(null)
    expect(rowsInStore[10]).toBe(null)
    expect(rowsInStore[11]).toBe(null)
    expect(rowsInStore[12]).toBe(null)
    expect(rowsInStore[13]).toBe(null)

    await store.dispatch('test/fetchMissingRowsInNewRange', {
      startIndex: 1,
      endIndex: 2,
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9]).toBe(null)
    expect(rowsInStore[10]).toBe(null)
    expect(rowsInStore[11]).toBe(null)
    expect(rowsInStore[12]).toBe(null)
    expect(rowsInStore[13]).toBe(null)

    await store.dispatch('test/fetchMissingRowsInNewRange', {
      startIndex: 10,
      endIndex: 11,
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9].id).toBe(10)
    expect(rowsInStore[10].id).toBe(11)
    expect(rowsInStore[11].id).toBe(12)
    expect(rowsInStore[12].id).toBe(13)
    expect(rowsInStore[13]).toBe(null)

    await store.dispatch('test/fetchMissingRowsInNewRange', {
      startIndex: 8,
      endIndex: 11,
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7].id).toBe(8)
    expect(rowsInStore[8].id).toBe(9)
    expect(rowsInStore[9].id).toBe(10)
    expect(rowsInStore[10].id).toBe(11)
    expect(rowsInStore[11].id).toBe(12)
    expect(rowsInStore[12].id).toBe(13)
    expect(rowsInStore[13]).toBe(null)

    store.state.test.rows[12]._ = { tmp: true }
    await store.dispatch('test/fetchMissingRowsInNewRange', {
      startIndex: 12,
      endIndex: 14,
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7].id).toBe(8)
    expect(rowsInStore[8].id).toBe(9)
    expect(rowsInStore[9].id).toBe(10)
    expect(rowsInStore[10].id).toBe(11)
    expect(rowsInStore[11].id).toBe(12)
    expect(rowsInStore[12].id).toBe(13)
    // Check if the state has not been overwritten.
    expect(rowsInStore[12]._.tmp).toBe(true)
    expect(rowsInStore[13].id).toBe(14)
  })

  test('refresh', async () => {
    const service = () => {
      return {
        fetchRows({ viewId, limit = 100, offset = null }) {
          const all = Array(30)
            .fill(null)
            .map((row, index) => {
              return { id: index + 1 }
            })

          const data = {
            results: all.slice(offset, offset + limit),
          }
          return { data }
        },
        fetchCount() {
          const data = { count: 30 }
          return { data }
        },
      }
    }
    const populateRow = (row) => {
      row._ = {}
      return row
    }
    const testStore = bufferedRows({ service, populateRow })

    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 10,
        endIndex: 13,
      },
      requestSize: 8,
      viewId: 1,
      rows: [
        { id: 1 },
        { id: 2 },
        { id: 3 },
        { id: 4 },
        { id: 5 },
        { id: 6 },
        { id: 7 },
        { id: 8 },
        { id: 9 },
        { id: 10 },
        { id: 11 },
        { id: 12 },
        { id: 13 },
        { id: 14 },
        { id: 15 },
        { id: 16 },
        { id: 17 },
        { id: 18 },
        { id: 19 },
        { id: 20 },
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/refresh', {})
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2]).toBe(null)
    expect(rowsInStore[3]).toBe(null)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(9)
    expect(rowsInStore[9].id).toBe(10)
    expect(rowsInStore[10].id).toBe(11)
    expect(rowsInStore[11].id).toBe(12)
    expect(rowsInStore[12].id).toBe(13)
    expect(rowsInStore[13].id).toBe(14)
    expect(rowsInStore[14].id).toBe(15)
    expect(rowsInStore[15].id).toBe(16)
    expect(rowsInStore[16]).toBe(null)
    expect(rowsInStore[17]).toBe(null)
    expect(rowsInStore[18]).toBe(null)
    expect(rowsInStore[19]).toBe(null)
  })

  test('refresh with less', async () => {
    const service = () => {
      return {
        fetchRows({ viewId, limit = 100, offset = null }) {
          const all = Array(10)
            .fill(null)
            .map((row, index) => {
              return { id: index + 1 }
            })

          const data = {
            results: all.slice(offset, offset + limit),
          }
          return { data }
        },
        fetchCount() {
          const data = { count: 10 }
          return { data }
        },
      }
    }
    const populateRow = (row) => {
      row._ = {}
      return row
    }
    const testStore = bufferedRows({ service, populateRow })

    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 9,
        endIndex: 12,
      },
      requestSize: 8,
      viewId: 1,
      rows: [
        { id: 1 },
        { id: 2 },
        { id: 3 },
        { id: 4 },
        { id: 5 },
        { id: 6 },
        { id: 7 },
        { id: 8 },
        { id: 9 },
        { id: 10 },
        { id: 11 },
        { id: 12 },
        { id: 13 },
        { id: 14 },
        { id: 15 },
        { id: 16 },
        { id: 17 },
        { id: 18 },
        { id: 19 },
        { id: 20 },
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/refresh', {})
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7].id).toBe(8)
    expect(rowsInStore[8].id).toBe(9)
    expect(rowsInStore[9].id).toBe(10)
  })

  test('refresh to empty', async () => {
    const service = () => {
      return {
        fetchRows({ viewId, limit = 100, offset = null }) {
          return { data: { results: [] } }
        },
        fetchCount() {
          return { data: { count: 0 } }
        },
      }
    }
    const populateRow = (row) => {
      row._ = {}
      return row
    }
    const testStore = bufferedRows({ service, populateRow })

    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 1,
      },
      requestSize: 2,
      viewId: 1,
      rows: [{ id: 1 }, { id: 2 }, null, null],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/refresh', {})
    expect(store.getters['test/getRows'].length).toBe(0)
    expect(store.getters['test/getVisibleRange']).toStrictEqual({
      startIndex: 0,
      endIndex: 0,
    })
  })

  test('find index of not existing row', async () => {
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
    ]
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        { id: 1, order: '1.00000000000000000000', field_1: 'Row 1' },
        { id: 2, order: '2.00000000000000000000', field_1: 'Row 2' },
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 4, order: '4.00000000000000000000', field_1: 'Row 4' },
        null,
        null,
        null,
        null,
        { id: 10, order: '10.00000000000000000000', field_1: 'Row 10' },
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    let index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 0,
        order: '0.00000000000000000000',
        field_1: 'Row 0',
      },
    })
    expect(index).toStrictEqual({ index: 0, isCertain: true })

    index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 5,
        order: '3.50000000000000000000',
        field_1: 'Row 5',
      },
    })
    expect(index).toStrictEqual({ index: 3, isCertain: true })

    index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 5,
        order: '5.00000000000000000000',
        field_1: 'Row 5',
      },
    })
    expect(index).toStrictEqual({ index: 8, isCertain: false })

    index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 13,
        order: '13.50000000000000000000',
        field_1: 'Row 13',
      },
    })
    expect(index).toStrictEqual({ index: 11, isCertain: true })

    index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 100,
        order: '100.00000000000000000000',
        field_1: 'Row 100',
      },
    })
    expect(index).toStrictEqual({ index: 12, isCertain: true })
  })

  test('find index of not existing row with null at beginning and end', async () => {
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
    ]
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        null,
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 5, order: '5.00000000000000000000', field_1: 'Row 5' },
        { id: 6, order: '6.00000000000000000000', field_1: 'Row 6' },
        { id: 7, order: '7.00000000000000000000', field_1: 'Row 7' },
        null,
        null,
        { id: 10, order: '10.00000000000000000000', field_1: 'Row 10' },
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    let index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Row 4',
      },
    })
    expect(index).toStrictEqual({ index: 3, isCertain: true })

    index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 2,
        order: '2.00000000000000000000',
        field_1: 'Row 2',
      },
    })
    expect(index).toStrictEqual({ index: 2, isCertain: false })

    index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 13,
        order: '13.00000000000000000000',
        field_1: 'Row 13',
      },
    })
    expect(index).toStrictEqual({ index: 11, isCertain: true })

    index = await store.dispatch('test/findIndexOfNotExistingRow', {
      view,
      fields,
      row: {
        id: 100,
        order: '100.00000000000000000000',
        field_1: 'Row 100',
      },
    })
    expect(index).toStrictEqual({ index: 14, isCertain: false })
  })

  test('find index of existing row', async () => {
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
    ]
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        { id: 1, order: '1.00000000000000000000', field_1: 'Row 1' },
        { id: 2, order: '2.00000000000000000000', field_1: 'Row 2' },
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 4, order: '4.00000000000000000000', field_1: 'Row 4' },
        null,
        null,
        null,
        null,
        { id: 10, order: '10.00000000000000000000', field_1: 'Row 10' },
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    let index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'Row 1',
      },
    })
    expect(index).toStrictEqual({ index: 0, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'Row 3',
      },
    })
    expect(index).toStrictEqual({ index: 2, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Row 4',
      },
    })
    expect(index).toStrictEqual({ index: 3, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 5,
        order: '5.00000000000000000000',
        field_1: 'Row 5',
      },
    })
    expect(index).toStrictEqual({ index: 7, isCertain: false })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 10,
        order: '10.00000000000000000000',
        field_1: 'Row 10',
      },
    })
    expect(index).toStrictEqual({ index: 8, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 14,
        order: '14.00000000000000000000',
        field_1: 'Row 14',
      },
    })
    expect(index).toStrictEqual({ index: 11, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 15,
        order: '15.00000000000000000000',
        field_1: 'Row 15',
      },
    })
    // This one is for sure not found.
    expect(index).toStrictEqual({ index: -1, isCertain: false })
  })

  test('find index of existing row with null at the start and end', async () => {
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
    ]
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        null,
        { id: 1, order: '1.00000000000000000000', field_1: 'Row 1' },
        { id: 2, order: '2.00000000000000000000', field_1: 'Row 2' },
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 4, order: '4.00000000000000000000', field_1: 'Row 4' },
        null,
        null,
        { id: 10, order: '10.00000000000000000000', field_1: 'Row 10' },
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    let index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'Row 1',
      },
    })
    expect(index).toStrictEqual({ index: 2, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 0,
        order: '0.00000000000000000000',
        field_1: 'Row 0',
      },
    })
    expect(index).toStrictEqual({ index: 1, isCertain: false })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Row 4',
      },
    })
    expect(index).toStrictEqual({ index: 5, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 6,
        order: '6.00000000000000000000',
        field_1: 'Row 6',
      },
    })
    expect(index).toStrictEqual({ index: 7, isCertain: false })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 12,
        order: '12.00000000000000000000',
        field_1: 'Row 12',
      },
    })
    expect(index).toStrictEqual({ index: 10, isCertain: true })

    index = await store.dispatch('test/findIndexOfExistingRow', {
      view,
      fields,
      row: {
        id: 15,
        order: '15.00000000000000000000',
        field_1: 'Row 15',
      },
    })
    expect(index).toStrictEqual({ index: 13, isCertain: false })
  })

  test('test row matches filters', async () => {
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

    const testStore = bufferedRows({ service: null, populateRow: null })
    store.registerModule('test', testStore)

    expect(
      await store.dispatch('test/rowMatchesFilters', {
        view,
        fields,
        row: { id: 12, order: '12.00000000000000000000', field_1: 'Value 12' },
      })
    ).toBe(true)
    expect(
      await store.dispatch('test/rowMatchesFilters', {
        view,
        fields,
        row: {
          id: 12,
          order: '12.00000000000000000000',
          field_1: 'Not matching 12',
        },
      })
    ).toBe(false)
    expect(
      await store.dispatch('test/rowMatchesFilters', {
        view,
        fields,
        row: {
          id: 12,
          order: '12.00000000000000000000',
          field_1: 'Not matching 12',
        },
        overrides: { field_1: 'Value' },
      })
    ).toBe(true)
    view.filters_disabled = true
    expect(
      await store.dispatch('test/rowMatchesFilters', {
        view,
        fields,
        row: {
          id: 12,
          order: '12.00000000000000000000',
          field_1: 'Not matching 12',
        },
      })
    ).toBe(true)
  })

  test('test created new row', async () => {
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
    ]
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 5, order: '5.00000000000000000000', field_1: 'Row 5' },
        { id: 6, order: '6.00000000000000000000', field_1: 'Row 6' },
        { id: 7, order: '7.00000000000000000000', field_1: 'Row 7' },
        null,
        { id: 10, order: '10.00000000000000000000', field_1: 'Row 10' },
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterNewRowCreated', {
      view,
      fields,
      values: {
        id: 2,
        order: '2.00000000000000000000',
        field_1: 'Row 2',
      },
    })
    let rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    // This is the newly created row. We couldn't be 100% sure this was the right
    // position, so it's added as null.
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(5)
    expect(rowsInStore[4].id).toBe(6)
    expect(rowsInStore[5].id).toBe(7)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7].id).toBe(10)
    expect(rowsInStore[8].id).toBe(11)
    expect(rowsInStore[9].id).toBe(12)
    expect(rowsInStore[10].id).toBe(14)
    expect(rowsInStore[11]).toBe(null)

    await store.dispatch('test/afterNewRowCreated', {
      view,
      fields,
      values: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Row 4',
      },
    })
    rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    // This is the newly created row. Because there was one before and after, we
    // were 100% sure the row was supposed to be at this position.
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(10)
    expect(rowsInStore[9].id).toBe(11)
    expect(rowsInStore[10].id).toBe(12)
    expect(rowsInStore[11].id).toBe(14)
    expect(rowsInStore[12]).toBe(null)

    await store.dispatch('test/afterNewRowCreated', {
      view,
      fields,
      values: {
        id: 13,
        order: '13.00000000000000000000',
        field_1: 'Row 13',
      },
    })
    rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(10)
    expect(rowsInStore[9].id).toBe(11)
    expect(rowsInStore[10].id).toBe(12)
    // We again know for sure the row was supposed to be at this position.
    expect(rowsInStore[11].id).toBe(13)
    expect(rowsInStore[12].id).toBe(14)
    expect(rowsInStore[13]).toBe(null)

    await store.dispatch('test/afterNewRowCreated', {
      view,
      fields,
      values: {
        id: 16,
        order: '16.00000000000000000000',
        field_1: 'Row 16',
      },
    })
    rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(10)
    expect(rowsInStore[9].id).toBe(11)
    expect(rowsInStore[10].id).toBe(12)
    expect(rowsInStore[11].id).toBe(13)
    expect(rowsInStore[12].id).toBe(14)
    expect(rowsInStore[13]).toBe(null)
    // We didn't know for sure that this was the last row, so it had to be added as
    // null.
    expect(rowsInStore[14]).toBe(null)

    store.getters['test/getRows'][14] = {
      id: 16,
      order: '16.00000000000000000000',
      field_1: 'Row 16',
    }
    await store.dispatch('test/afterNewRowCreated', {
      view,
      fields,
      values: {
        id: 17,
        order: '17.00000000000000000000',
        field_1: 'Row 17',
      },
    })
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(10)
    expect(rowsInStore[9].id).toBe(11)
    expect(rowsInStore[10].id).toBe(12)
    expect(rowsInStore[11].id).toBe(13)
    expect(rowsInStore[12].id).toBe(14)
    expect(rowsInStore[13]).toBe(null)
    expect(rowsInStore[14].id).toBe(16)
    // Because we've made id 16 known and it was the last item, we do know for sure
    // where 17 belonged.
    expect(rowsInStore[15].id).toBe(17)

    store.getters['test/getRows'][0] = {
      id: 1,
      order: '1.00000000000000000000',
      field_1: 'Row 1',
    }
    await store.dispatch('test/afterNewRowCreated', {
      view,
      fields,
      values: {
        id: 0,
        order: '0.00000000000000000000',
        field_1: 'Row 0',
      },
    })
    // Because we've made first row known, we know for sure if one needs to be
    // placed first.
    expect(rowsInStore[0].id).toBe(0)
    expect(rowsInStore[1].id).toBe(1)
    expect(rowsInStore[2]).toBe(null)
    expect(rowsInStore[3].id).toBe(3)
    expect(rowsInStore[4].id).toBe(4)
    expect(rowsInStore[5].id).toBe(5)
    expect(rowsInStore[6].id).toBe(6)
    expect(rowsInStore[7].id).toBe(7)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9].id).toBe(10)
    expect(rowsInStore[10].id).toBe(11)
    expect(rowsInStore[11].id).toBe(12)
    expect(rowsInStore[12].id).toBe(13)
    expect(rowsInStore[13].id).toBe(14)
    expect(rowsInStore[14]).toBe(null)
    expect(rowsInStore[15].id).toBe(16)
    expect(rowsInStore[16].id).toBe(17)
  })

  test('test created new row ignored if filtered', async () => {
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
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 5, order: '5.00000000000000000000', field_1: 'Row 5' },
        { id: 6, order: '6.00000000000000000000', field_1: 'Row 6' },
        { id: 7, order: '7.00000000000000000000', field_1: 'Row 7' },
        null,
        { id: 10, order: '10.00000000000000000000', field_1: 'Row 10' },
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterNewRowCreated', {
      view,
      fields,
      values: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Row 2',
      },
    })
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1].id).toBe(3)
    expect(rowsInStore[2].id).toBe(5)
    expect(rowsInStore[3].id).toBe(6)
    expect(rowsInStore[4].id).toBe(7)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6].id).toBe(10)
    expect(rowsInStore[7].id).toBe(11)
    expect(rowsInStore[8].id).toBe(12)
    expect(rowsInStore[9].id).toBe(14)
    expect(rowsInStore[10]).toBe(null)
  })

  test('test updated existing row without filters', async () => {
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
    ]
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        {
          id: 5,
          order: '5.00000000000000000000',
          field_1: 'Row 5',
          _: { tmp: true },
        },
        { id: 6, order: '6.00000000000000000000', field_1: 'Row 6' },
        { id: 7, order: '7.00000000000000000000', field_1: 'Row 7' },
        null,
        null,
        null,
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 5,
        order: '5.00000000000000000000',
        field_1: 'Row 5',
      },
      values: {
        field_1: 'Row 5 updated',
      },
    })
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1].id).toBe(3)
    expect(rowsInStore[2].id).toBe(5)
    expect(rowsInStore[2]._.tmp).toBe(true)
    expect(rowsInStore[2].field_1).toBe('Row 5 updated')
    expect(rowsInStore[3].id).toBe(6)
    expect(rowsInStore[4].id).toBe(7)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(11)
    expect(rowsInStore[9].id).toBe(12)
    expect(rowsInStore[10].id).toBe(14)
    expect(rowsInStore[11]).toBe(null)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 5,
        order: '5.00000000000000000000',
        field_1: 'Row 5 updated',
      },
      values: {
        order: '6.50000000000000000000',
      },
    })
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1].id).toBe(3)
    expect(rowsInStore[2].id).toBe(6)
    expect(rowsInStore[3].id).toBe(5)
    expect(rowsInStore[3]._.tmp).toBe(true)
    expect(rowsInStore[4].id).toBe(7)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(11)
    expect(rowsInStore[9].id).toBe(12)
    expect(rowsInStore[10].id).toBe(14)
    expect(rowsInStore[11]).toBe(null)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 5,
        order: '6.50000000000000000000',
        field_1: 'Row 5 updated',
      },
      values: {
        order: '7.50000000000000000000',
      },
    })
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1].id).toBe(3)
    expect(rowsInStore[2].id).toBe(6)
    expect(rowsInStore[3].id).toBe(7)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(11)
    expect(rowsInStore[9].id).toBe(12)
    expect(rowsInStore[10].id).toBe(14)
    expect(rowsInStore[11]).toBe(null)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 5,
        order: '7.50000000000000000000',
        field_1: 'Row 5 updated',
      },
      values: {
        order: '14.50000000000000000000',
      },
    })
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1].id).toBe(3)
    expect(rowsInStore[2].id).toBe(6)
    expect(rowsInStore[3].id).toBe(7)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7].id).toBe(11)
    expect(rowsInStore[8].id).toBe(12)
    expect(rowsInStore[9].id).toBe(14)
    expect(rowsInStore[10]).toBe(null)
    expect(rowsInStore[11]).toBe(null)
  })

  test('test updated existing row with filters', async () => {
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
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 5, order: '5.00000000000000000000', field_1: 'Row 5' },
        { id: 6, order: '6.00000000000000000000', field_1: 'Row 6' },
        { id: 7, order: '7.00000000000000000000', field_1: 'Row 7' },
        null,
        null,
        null,
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'Row 1',
      },
      values: {
        field_1: 'Row 1 value',
      },
    })
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(5)
    expect(rowsInStore[4].id).toBe(6)
    expect(rowsInStore[5].id).toBe(7)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9].id).toBe(11)
    expect(rowsInStore[10].id).toBe(12)
    expect(rowsInStore[11].id).toBe(14)
    expect(rowsInStore[12]).toBe(null)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Row 4',
      },
      values: {
        field_1: 'Row 4 value',
      },
    })
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)
    expect(rowsInStore[4].id).toBe(5)
    expect(rowsInStore[5].id).toBe(6)
    expect(rowsInStore[6].id).toBe(7)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9]).toBe(null)
    expect(rowsInStore[10].id).toBe(11)
    expect(rowsInStore[11].id).toBe(12)
    expect(rowsInStore[12].id).toBe(14)
    expect(rowsInStore[13]).toBe(null)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 4,
        order: '4.00000000000000000000',
        field_1: 'Row 4 value',
      },
      values: {
        field_1: 'Row 4',
      },
    })
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(5)
    expect(rowsInStore[4].id).toBe(6)
    expect(rowsInStore[5].id).toBe(7)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9].id).toBe(11)
    expect(rowsInStore[10].id).toBe(12)
    expect(rowsInStore[11].id).toBe(14)
    expect(rowsInStore[12]).toBe(null)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 15,
        order: '15.00000000000000000000',
        field_1: 'Row 15 value',
      },
      values: {
        field_1: 'Row 15',
      },
    })
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1]).toBe(null)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(5)
    expect(rowsInStore[4].id).toBe(6)
    expect(rowsInStore[5].id).toBe(7)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8]).toBe(null)
    expect(rowsInStore[9].id).toBe(11)
    expect(rowsInStore[10].id).toBe(12)
    expect(rowsInStore[11].id).toBe(14)
  })

  test('test updated existing row with sorting', async () => {
    const view = {
      id: 1,
      filters_disabled: false,
      filter_type: 'AND',
      filters: [],
      sortings: [
        {
          id: 1,
          view: 1,
          field: 1,
          order: 'ASC',
          type: 'default',
        },
      ],
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
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        { id: 1, order: '1.00000000000000000000', field_1: 'A' },
        { id: 2, order: '2.00000000000000000000', field_1: 'B' },
        { id: 3, order: '3.00000000000000000000', field_1: 'C' },
        { id: 4, order: '4.00000000000000000000', field_1: 'D' },
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'C',
      },
      values: {
        field_1: 'C2',
      },
    })
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'C2',
      },
      values: {
        field_1: 'C',
      },
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(3)
    expect(rowsInStore[3].id).toBe(4)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'C',
      },
      values: {
        field_1: 'E',
      },
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(4)
    expect(rowsInStore[3].id).toBe(3)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'E',
      },
      values: {
        field_1: '0',
      },
    })
    expect(rowsInStore[0].id).toBe(3)
    expect(rowsInStore[1].id).toBe(1)
    expect(rowsInStore[2].id).toBe(2)
    expect(rowsInStore[3].id).toBe(4)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: '0',
      },
      values: {
        field_1: '0',
      },
    })
    expect(rowsInStore[0].id).toBe(3)
    expect(rowsInStore[1].id).toBe(1)
    expect(rowsInStore[2].id).toBe(2)
    expect(rowsInStore[3].id).toBe(4)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: '0',
      },
      values: {
        field_1: 'A1',
      },
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(3)
    expect(rowsInStore[2].id).toBe(2)
    expect(rowsInStore[3].id).toBe(4)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 3,
        order: '3.00000000000000000000',
        field_1: 'A1',
      },
      values: {
        field_1: 'D1',
      },
    })
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(4)
    expect(rowsInStore[3].id).toBe(3)
  })

  test('test updated existing with sorting from null', async () => {
    const view = {
      id: 1,
      filters_disabled: false,
      filter_type: 'AND',
      filters: [],
      sortings: [
        {
          id: 1,
          view: 1,
          field: 1,
          order: 'ASC',
          type: 'default',
        },
      ],
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
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        { id: 1, order: '1.00000000000000000000', field_1: '1' },
        { id: 2, order: '2.00000000000000000000', field_1: '2' },
        { id: 3, order: '3.00000000000000000000', field_1: '3' },
        { id: 4, order: '4.00000000000000000000', field_1: '4' },
        null,
        null,
        null,
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterExistingRowUpdated', {
      view,
      fields,
      row: {
        id: 7,
        order: '7.00000000000000000000',
        field_1: '7',
      },
      values: {
        field_1: '22',
      },
    })
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0].id).toBe(1)
    expect(rowsInStore[1].id).toBe(2)
    expect(rowsInStore[2].id).toBe(7)
    expect(rowsInStore[3].id).toBe(3)
    expect(rowsInStore[4].id).toBe(4)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
  })

  test('test deleted existing row', async () => {
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
    ]
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 5, order: '5.00000000000000000000', field_1: 'Row 5' },
        { id: 6, order: '6.00000000000000000000', field_1: 'Row 6' },
        { id: 7, order: '7.00000000000000000000', field_1: 'Row 7' },
        null,
        null,
        null,
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterExistingRowDeleted', {
      view,
      fields,
      row: {
        id: 1,
        order: '1.00000000000000000000',
        field_1: 'Row 1',
      },
    })
    const rowsInStore = store.getters['test/getRows']
    expect(rowsInStore[0].id).toBe(3)
    expect(rowsInStore[1].id).toBe(5)
    expect(rowsInStore[2].id).toBe(6)
    expect(rowsInStore[3].id).toBe(7)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7].id).toBe(11)
    expect(rowsInStore[8].id).toBe(12)
    expect(rowsInStore[9].id).toBe(14)
    expect(rowsInStore[10]).toBe(null)

    await store.dispatch('test/afterExistingRowDeleted', {
      view,
      fields,
      row: {
        id: 15,
        order: '15.00000000000000000000',
        field_1: 'Row 15',
      },
    })
    expect(rowsInStore[0].id).toBe(3)
    expect(rowsInStore[1].id).toBe(5)
    expect(rowsInStore[2].id).toBe(6)
    expect(rowsInStore[3].id).toBe(7)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7].id).toBe(11)
    expect(rowsInStore[8].id).toBe(12)
    expect(rowsInStore[9].id).toBe(14)

    await store.dispatch('test/afterExistingRowDeleted', {
      view,
      fields,
      row: {
        id: 9,
        order: '9.00000000000000000000',
        field_1: 'Row 9',
      },
    })
    expect(rowsInStore[0].id).toBe(3)
    expect(rowsInStore[1].id).toBe(5)
    expect(rowsInStore[2].id).toBe(6)
    expect(rowsInStore[3].id).toBe(7)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6].id).toBe(11)
    expect(rowsInStore[7].id).toBe(12)
    expect(rowsInStore[8].id).toBe(14)

    await store.dispatch('test/afterExistingRowDeleted', {
      view,
      fields,
      row: {
        id: 5,
        order: '5.00000000000000000000',
        field_1: 'Row 5',
      },
    })
    expect(rowsInStore[0].id).toBe(3)
    expect(rowsInStore[1].id).toBe(6)
    expect(rowsInStore[2].id).toBe(7)
    expect(rowsInStore[3]).toBe(null)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5].id).toBe(11)
    expect(rowsInStore[6].id).toBe(12)
    expect(rowsInStore[7].id).toBe(14)

    await store.dispatch('test/afterExistingRowDeleted', {
      view,
      fields,
      row: {
        id: 14,
        order: '14.00000000000000000000',
        field_1: 'Row 14',
      },
    })
    expect(rowsInStore[0].id).toBe(3)
    expect(rowsInStore[1].id).toBe(6)
    expect(rowsInStore[2].id).toBe(7)
    expect(rowsInStore[3]).toBe(null)
    expect(rowsInStore[4]).toBe(null)
    expect(rowsInStore[5].id).toBe(11)
    expect(rowsInStore[6].id).toBe(12)
  })

  test('test deleted existing row ignored if filtered', async () => {
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
    const populateRow = (row) => {
      row._ = {}
      return row
    }

    const testStore = bufferedRows({ service: null, populateRow })
    const state = Object.assign(testStore.state(), {
      visibleRange: {
        startIndex: 0,
        endIndex: 0,
      },
      requestSize: 4,
      viewId: 1,
      rows: [
        null,
        { id: 3, order: '3.00000000000000000000', field_1: 'Row 3' },
        { id: 5, order: '5.00000000000000000000', field_1: 'Row 5' },
        { id: 6, order: '6.00000000000000000000', field_1: 'Row 6' },
        { id: 7, order: '7.00000000000000000000', field_1: 'Row 7' },
        null,
        null,
        null,
        { id: 11, order: '11.00000000000000000000', field_1: 'Row 11' },
        { id: 12, order: '12.00000000000000000000', field_1: 'Row 12' },
        { id: 14, order: '14.00000000000000000000', field_1: 'Row 14' },
        null,
      ],
    })
    testStore.state = () => state
    store.registerModule('test', testStore)

    await store.dispatch('test/afterExistingRowDeleted', {
      view,
      fields,
      row: {
        id: 100,
        order: '100.00000000000000000000',
        field_1: 'Row 1',
      },
    })
    const rowsInStore = store.getters['test/getRows']
    // Nothing should have been updated because the deleted row didn't match the
    // filters.
    expect(rowsInStore[0]).toBe(null)
    expect(rowsInStore[1].id).toBe(3)
    expect(rowsInStore[2].id).toBe(5)
    expect(rowsInStore[3].id).toBe(6)
    expect(rowsInStore[4].id).toBe(7)
    expect(rowsInStore[5]).toBe(null)
    expect(rowsInStore[6]).toBe(null)
    expect(rowsInStore[7]).toBe(null)
    expect(rowsInStore[8].id).toBe(11)
    expect(rowsInStore[9].id).toBe(12)
    expect(rowsInStore[10].id).toBe(14)
    expect(rowsInStore[11]).toBe(null)
  })
})

describe('Buffered rows search', () => {
  let testApp = null
  let store = null
  let bufferedRowsModule = null
  let view = null
  const storeName = 'test'
  const activeSearchTerm = 'searchterm'

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    bufferedRowsModule = bufferedRows({ service: null, populateRow: null })
    view = createView()
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('Rows are fetched on refresh based on search term', async () => {
    const serviceStub = () => {
      return {
        fetchRows(params) {
          if (params.search === activeSearchTerm) {
            return {
              data: {
                results: [
                  {
                    id: 1,
                    order: '1.00000000000000000000',
                    field_1: 'Row matching search',
                  },
                ],
              },
            }
          }
          return {
            data: {
              results: [
                {
                  id: 1,
                  order: '1.00000000000000000000',
                  field_1: 'Row matching search',
                },
                {
                  id: 2,
                  order: '2.00000000000000000000',
                  field_1: 'Row not search',
                },
              ],
            },
          }
        },
        fetchCount(params) {
          if (params.search === activeSearchTerm) {
            return { data: { count: 1 } }
          }
          return { data: { count: 2 } }
        },
      }
    }
    bufferedRowsModule = bufferedRows({
      service: serviceStub,
      populateRow: null,
    })
    const state = Object.assign(bufferedRowsModule.state(), {
      viewId: view.id,
      rows: [],
      activeSearchTerm,
    })
    bufferedRowsModule.state = () => state
    store.registerModule(storeName, bufferedRowsModule)

    await store.dispatch(`${storeName}/refresh`, {
      fields: [createPrimaryField()],
    })

    const rowsInStore = store.getters[`${storeName}/getRows`]
    expect(rowsInStore.length).toBe(1)
  })

  test('A new row matching search has been added', async () => {
    const state = Object.assign(bufferedRowsModule.state(), {
      viewId: view.id,
      rows: [{ id: 2, order: '2.00000000000000000000', field_1: 'Row 2' }],
      activeSearchTerm,
    })
    bufferedRowsModule.state = () => state
    store.registerModule(storeName, bufferedRowsModule)

    const newMatchingRow = {
      id: 1,
      order: '1.00000000000000000000',
      field_1: `matching the ${activeSearchTerm}`,
    }

    await store.dispatch(`${storeName}/afterNewRowCreated`, {
      view,
      fields: [createPrimaryField()],
      values: newMatchingRow,
    })

    const rowsInStore = store.getters[`${storeName}/getRows`]
    expect(rowsInStore[0].id).toBe(newMatchingRow.id)
  })

  test('A new row not matching search has not been added', async () => {
    const state = Object.assign(bufferedRowsModule.state(), {
      viewId: view.id,
      rows: [{ id: 2, order: '2.00000000000000000000', field_1: 'Row 2' }],
      activeSearchTerm,
    })
    bufferedRowsModule.state = () => state
    store.registerModule(storeName, bufferedRowsModule)

    const newNotMatchingRow = {
      id: 1,
      order: '1.00000000000000000000',
      field_1: `not matching`,
    }

    await store.dispatch(`${storeName}/afterNewRowCreated`, {
      view,
      fields: [],
      values: newNotMatchingRow,
    })

    const rowsInStore = store.getters[`${storeName}/getRows`]
    expect(rowsInStore[0].id).not.toBe(newNotMatchingRow.id)
  })

  test('A row not matching search anymore has been removed', async () => {
    const matchingRow = {
      id: 2,
      order: '2.00000000000000000000',
      field_1: `matching the ${activeSearchTerm}`,
    }
    const state = Object.assign(bufferedRowsModule.state(), {
      viewId: view.id,
      rows: [matchingRow],
      activeSearchTerm,
    })
    bufferedRowsModule.state = () => state
    store.registerModule(storeName, bufferedRowsModule)

    const newValues = {
      field_1: 'not matching',
    }

    await store.dispatch(`${storeName}/afterExistingRowUpdated`, {
      view,
      fields: [createPrimaryField()],
      row: matchingRow,
      values: newValues,
    })

    const rowsInStore = store.getters[`${storeName}/getRows`]
    expect(rowsInStore[0]).toBeUndefined()
  })
})
