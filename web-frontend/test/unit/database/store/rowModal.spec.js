import rowModal from '@baserow/modules/database/store/rowModal'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('rowModal store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    //store = testApp.store
    store = testApp.createStore({
      modules: {
        test: {
          ...rowModal,
          state: () => ({
            rows: [],
          }),
        },
      },
    })
  })

  afterEach(() => {
    testApp.afterEach()
  })

  test('get not existing component id', () => {
    const values = store.getters['test/get'](-1)
    expect(values).toMatchObject({
      id: -1,
      tableId: -1,
      exists: false,
      row: {},
    })
  })

  test('open row', async () => {
    await store.dispatch('test/open', {
      componentId: 1,
      tableId: 10,
      id: 100,
      exists: true,
      row: { id: 100, field_1: 'Test' },
    })
    await store.dispatch('test/open', {
      componentId: 2,
      tableId: 20,
      id: 200,
      exists: true,
      row: { id: 200, field_2: 'Test' },
    })
    const valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1).toMatchObject({
      tableId: 10,
      id: 100,
      exists: true,
      row: { id: 100, field_1: 'Test' },
    })
    const valuesOfComponent2 = store.getters['test/get'](2)
    expect(valuesOfComponent2).toMatchObject({
      tableId: 20,
      id: 200,
      exists: true,
      row: { id: 200, field_2: 'Test' },
    })
  })

  test('open rows', async () => {
    await store.dispatch('test/open', {
      componentId: 1,
      tableId: 10,
      id: 100,
      exists: true,
      row: { id: 100, field_1: 'Test' },
    })
    await store.dispatch('test/open', {
      componentId: 2,
      tableId: 20,
      id: 200,
      exists: true,
      row: { id: 200, field_2: 'Test' },
    })
    const valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1).toMatchObject({
      tableId: 10,
      id: 100,
      exists: true,
      row: { id: 100, field_1: 'Test' },
    })
    const valuesOfComponent2 = store.getters['test/get'](2)
    expect(valuesOfComponent2).toMatchObject({
      tableId: 20,
      id: 200,
      exists: true,
      row: { id: 200, field_2: 'Test' },
    })
  })

  test('clear row', async () => {
    await store.dispatch('test/open', {
      componentId: 1,
      tableId: 10,
      id: 100,
      exists: true,
      row: { id: 100, field_1: 'Test' },
    })
    await store.dispatch('test/clear', {
      componentId: 1,
    })
    const valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1).toMatchObject({
      id: -1,
      tableId: -1,
      exists: false,
      row: {},
    })
    // Clearing a component id that doesn't exist shouldn't fail.
    await store.dispatch('test/clear', {
      componentId: 2,
    })
  })

  test('row does not exist', async () => {
    await store.dispatch('test/open', {
      componentId: 1,
      tableId: 10,
      id: 100,
      exists: true,
      row: { id: 100, field_1: 'Test' },
    })
    await store.dispatch('test/doesNotExist', {
      componentId: 1,
    })
    const valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1.exists).toBe(false)
  })

  test('row exists', async () => {
    await store.dispatch('test/open', {
      componentId: 1,
      tableId: 10,
      id: 100,
      exists: false,
      row: { id: 100, field_1: 'Test' },
    })
    const row = { id: 100, field_1: 'Test' }
    await store.dispatch('test/doesExist', {
      componentId: 1,
      row,
    })
    // Changing this row object should be reflected in the row in the store because
    // it's the same object.
    row.field_1 = 'Test 2'
    const valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1.row.field_1).toBe('Test 2')
  })

  test('rows exist', async () => {
    await store.dispatch('test/open', {
      componentId: 1,
      tableId: 10,
      id: 100,
      exists: true,
      row: { id: 100, field_1: 'Test' },
    })

    // Because `exists` is true, the row shouldn't be updated because it's managed
    // via another process.
    await store.dispatch('test/updated', {
      tableId: 10,
      values: { id: 100, field_1: 'Test 2' },
    })
    let valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1.row.field_1).toBe('Test')

    // Because `exists` is false, the row is managed by the store, so when an update
    // action is dispatched it should update the row.
    await store.dispatch('test/doesNotExist', { componentId: 1 })
    await store.dispatch('test/updated', {
      tableId: 10,
      values: { id: 100, field_1: 'Test 2' },
    })
    valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1.row.field_1).toBe('Test 2')

    // Because the table id doesn't match, we don't expect the value to be updated.
    await store.dispatch('test/updated', {
      tableId: 11,
      values: { id: 100, field_1: 'Test 3' },
    })
    valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1.row.field_1).toBe('Test 2')

    // Because the row id doesn't match, we don't expect the value to be updated.
    await store.dispatch('test/updated', {
      tableId: 10,
      values: { id: 101, field_1: 'Test 4' },
    })
    valuesOfComponent1 = store.getters['test/get'](1)
    expect(valuesOfComponent1.row.field_1).toBe('Test 2')
  })
})
