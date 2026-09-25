import flushPromises from 'flush-promises'
import gridStore, {
  populateRow,
} from '@baserow/modules/database/store/view/grid'
import { registerRealtimeEvents } from '@baserow/modules/database/realtime'
import { TestApp } from '@baserow/test/helpers/testApp'
import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'

describe('Grid realtime changes during row creation', () => {
  let testApp
  let store
  let gridType
  let view
  let fields
  let existingRows
  let savedRow
  let finishCreate
  let creating
  let finishUpdate
  let updating

  beforeEach(() => {
    testApp = new TestApp()
    gridType = testApp.getRegistry().get('view', 'grid')
    fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
    ]
    // Restricted-view filters are deliberately absent from the client payload.
    view = {
      id: 1,
      type: 'grid',
      table_id: 1,
      ownership_type: 'restricted',
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      filters_disabled: true,
      sortings: [],
      group_bys: [],
    }
    store = testApp.createStore({
      modules: {
        table: {
          namespaced: true,
          getters: { getSelected: () => ({ id: 1 }) },
        },
        field: { namespaced: true, getters: { getAll: () => fields } },
        view: {
          namespaced: true,
          state: () => ({ selected: view }),
          getters: {
            getSelected: (state) => state.selected,
            get: () => () => view,
          },
        },
        page: {
          namespaced: true,
          modules: {
            view: {
              namespaced: true,
              modules: {
                grid: {
                  ...gridStore,
                  actions: {
                    ...gridStore.actions,
                    async fetchByScrollTopDelayed({ dispatch }, args) {
                      await dispatch('fetchByScrollTop', args)
                      await dispatch('visibleByScrollTop', args.scrollTop)
                    },
                    fetchAllFieldAggregationData: vi.fn(),
                    fetchAllFieldAggregationDataDebounced: vi.fn(),
                  },
                },
              },
            },
          },
        },
        rowModal: { namespaced: true, actions: { updated: vi.fn() } },
      },
    })
    finishCreate = undefined
    creating = undefined
    finishUpdate = undefined
    updating = undefined
  })

  afterEach(async () => {
    // Also release the real mutation queue if an assertion fails mid-request.
    finishCreate?.()
    finishUpdate?.()
    await creating?.catch(() => {})
    await updating?.catch(() => {})
    await flushPromises()
    await testApp.afterEach()
  })

  const dispatch = (action, payload) =>
    store.dispatch(`page/view/grid/${action}`, payload)
  const get = (name) => store.getters[`page/view/grid/${name}`]
  const ids = () => get('getRows').map((row) => row.id)
  const rowCreated = (row) =>
    gridType.rowCreated({ store }, 1, fields, row, {}, 'page/')
  const rowDeleted = (row) =>
    gridType.rowDeleted({ store }, 1, fields, row, 'page/')

  async function startCreate(
    placement = 'bottom',
    status = 200,
    grouped = false
  ) {
    existingRows =
      placement === 'empty'
        ? []
        : [
            { id: 10, order: '1.00', field_1: 'Existing A' },
            { id: 11, order: '2.00', field_1: 'Existing B' },
          ]
    if (grouped) {
      fields.push({
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      })
      view.group_bys = [{ field: 2, order: 'ASC', type: 'default' }]
      existingRows.forEach((row) => {
        row.field_2 = 'A'
      })
    }
    store.state.page.view.grid = {
      ...gridStore.state(),
      lastGridId: 1,
      rows: existingRows.map((row) => populateRow({ ...row })),
      count: existingRows.length,
      bufferLimit: existingRows.length,
      windowHeight: 600,
    }
    savedRow = {
      id: 99,
      order:
        placement === 'before'
          ? '0.99999999'
          : placement === 'empty'
            ? '1.00'
            : '3.00',
      field_1: 'Created',
      ...(grouped ? { field_2: 'A' } : {}),
    }
    if (grouped) {
      Object.assign(store.state.page.view.grid, {
        rows: [],
        activeGroupBys: view.group_bys,
        fieldOptions: {
          1: { hidden: false, order: 0 },
          2: { hidden: false, order: 1 },
        },
        groupBy: {
          ...gridStore.state().groupBy,
          treeNodes: [
            {
              path: { field_2: 'A' },
              depth: 0,
              row_count: existingRows.length,
            },
          ],
          collapse: { mode: 'expand', paths: [] },
        },
      })
      store.commit('page/view/grid/SET_GROUP_BY_SECTION_ROWS', {
        sectionKey: pathKey({ field_2: 'A' }, [{ id: 2 }]),
        rows: existingRows.map((row) => populateRow({ ...row })),
        startPosition: 0,
      })
    }
    testApp.mockServer.mock.onGet('/database/views/grid/1/').reply(() => [
      200,
      {
        count: existingRows.length,
        results: existingRows,
        field_options: {},
      },
    ])
    testApp.mockServer.mock.onPost('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          finishCreate = () =>
            resolve([
              status,
              { items: [savedRow], metadata: { updated_field_ids: [] } },
            ])
        })
    )
    creating = dispatch('createNewRows', {
      view,
      table: { id: 1 },
      fields,
      rows: [{ field_1: 'Created', ...(grouped ? { field_2: 'A' } : {}) }],
      before: placement === 'before' ? existingRows[0] : null,
      ...(grouped ? { groupPath: { field_2: 'A' } } : {}),
    })
    await vi.waitFor(() => expect(finishCreate).toBeTypeOf('function'))
    await dispatch('visibleByScrollTop', 0)
  }

  test.each(['empty', 'bottom', 'before'])(
    'removes a new row when deletion arrives before its response (%s)',
    async (placement) => {
      await startCreate(placement)
      const deleting = rowDeleted(savedRow)
      await flushPromises()
      finishCreate()
      await Promise.all([creating, deleting])
      await flushPromises()

      expect(ids()).toEqual(existingRows.map((row) => row.id))
      expect(get('getCount')).toBe(existingRows.length)
      expect(get('getAllRows').some((row) => row.id === savedRow.id)).toBe(
        false
      )

      // A later filter reentry/undo must add the row exactly once.
      await rowCreated(savedRow)
      const expected =
        placement === 'before'
          ? [99, ...existingRows.map((row) => row.id)]
          : [...existingRows.map((row) => row.id), 99]
      expect(ids()).toEqual(expected)
      expect(get('getCount')).toBe(expected.length)
    }
  )

  test.each(['empty', 'bottom', 'before'])(
    'preserves deletion and reentry order when both precede the response (%s)',
    async (placement) => {
      await startCreate(placement)
      const deleting = rowDeleted(savedRow)
      const restoring = rowCreated(savedRow)
      await flushPromises()
      finishCreate()
      await Promise.all([creating, deleting, restoring])
      await flushPromises()

      const expected =
        placement === 'before'
          ? [99, ...existingRows.map((row) => row.id)]
          : [...existingRows.map((row) => row.id), 99]
      expect(ids()).toEqual(expected)
      expect(get('getAllRows').map((row) => row.id)).toEqual(expected)
      expect(get('getCount')).toBe(expected.length)
    }
  )

  test('applies an update after creation even if the temporary row is offscreen', async () => {
    await startCreate()
    store.state.page.view.grid.rowsEndIndex = 2
    const updating = gridType.rowUpdated(
      { store },
      1,
      fields,
      savedRow,
      { ...savedRow, field_1: 'Changed' },
      {},
      [],
      'page/'
    )
    await flushPromises()
    finishCreate()
    await Promise.all([creating, updating])
    expect(get('getRow')(99).field_1).toBe('Changed')
    expect(get('getCount')).toBe(3)
  })

  test('continues processing events after a failed creation', async () => {
    testApp.dontFailOnErrorResponses()
    await startCreate('bottom', 500)
    const rejected = creating.catch((error) => error)
    const deleting = rowDeleted(existingRows[0])
    const restoring = rowCreated(existingRows[0])
    finishCreate()
    const [error] = await Promise.all([rejected, deleting, restoring])
    expect(error).toBeInstanceOf(Error)
    await flushPromises()
    expect(ids()).toEqual([10, 11])
    expect(get('getCount')).toBe(2)
    expect(get('getAllRows').every((row) => typeof row.id === 'number')).toBe(
      true
    )
  })

  async function startUpdate(nonOptimistic = false) {
    await startCreate()
    finishCreate()
    await creating
    if (nonOptimistic) {
      fields.push({
        id: 2,
        name: 'Created on',
        type: 'created_on',
        date_format: 'ISO',
        date_include_time: true,
        _: { type: { type: 'created_on' } },
      })
      view.sortings = [{ field: 2, order: 'ASC', type: 'default' }]
    }
    testApp.mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          finishUpdate = () =>
            resolve([
              200,
              {
                items: [
                  { ...existingRows[0], field_1: 'Own edit', field_2: null },
                ],
                metadata: { updated_field_ids: [1] },
              },
            ])
        })
    )
    updating = dispatch('updateRowValue', {
      table: { id: 1 },
      view,
      row: get('getRow')(10),
      field: fields[0],
      fields,
      value: 'Own edit',
      oldValue: existingRows[0].field_1,
    })
    await vi.waitFor(() => expect(finishUpdate).toBeTypeOf('function'))
  }

  test('applies a visibility deletion before the local edit response returns', async () => {
    await startUpdate()
    const deleting = rowDeleted(existingRows[0])
    await flushPromises()
    expect(ids()).toEqual([11, 99])
    expect(get('getCount')).toBe(2)

    finishUpdate()
    await Promise.all([updating, deleting])
    await flushPromises()
    expect(ids()).toEqual([11, 99])
    expect(get('getCount')).toBe(2)
  })

  test('applies a newer realtime update after a pending non-optimistic edit', async () => {
    await startUpdate(true)
    expect(get('getRow')(10)._.loading).toBe(true)
    const realtimeUpdate = gridType.rowUpdated(
      { store },
      1,
      fields,
      { ...existingRows[0], field_1: 'Own edit', field_2: null },
      { ...existingRows[0], field_1: 'Newer edit', field_2: null },
      {},
      [1],
      'page/'
    )
    await flushPromises()
    expect(get('getRow')(10).field_1).not.toBe('Newer edit')
    finishUpdate()
    await Promise.all([updating, realtimeUpdate])
    expect(get('getRow')(10).field_1).toBe('Newer edit')
    expect(get('getCount')).toBe(3)
  })

  test('preserves grouped row locations and counts through pending deletion and reentry', async () => {
    await startCreate('bottom', 200, true)
    const deleting = rowDeleted(savedRow)
    const restoring = rowCreated(savedRow)
    finishCreate()
    await Promise.all([creating, deleting, restoring])
    await flushPromises()
    const sectionKey = pathKey({ field_2: 'A' }, [{ id: 2 }])
    const group = store.state.page.view.grid.groupBy
    expect(group.sectionRows[sectionKey].map((row) => row.id)).toEqual([
      10, 11, 99,
    ])
    expect(group.rowLocations[99]).toEqual({ sectionKey, position: 2 })
    expect(group.treeNodes[0].row_count).toBe(3)
    expect(get('getCount')).toBe(3)
  })

  test.each([false, true])(
    'discards queued events after switching views (return=%s)',
    async (returnToView) => {
      await startCreate()
      const deleting = rowDeleted(existingRows[0])
      // A new initial fetch replaces the grid contents, possibly with a different
      // restricted filter on the same table. Returning to the same ID also refetches.
      store.state.view.selected = { ...view, id: 2 }
      store.commit('page/view/grid/SET_LAST_GRID_ID', 2)
      if (returnToView) {
        store.state.view.selected = view
        store.commit('page/view/grid/SET_LAST_GRID_ID', 1)
      }
      store.commit('page/view/grid/CLEAR_ROWS')
      store.commit('page/view/grid/ADD_ROWS', {
        rows: existingRows.map((row) => populateRow({ ...row })),
        count: 2,
        bufferStartIndex: 0,
        bufferLimit: 2,
        prependToRows: 0,
        appendToRows: 2,
      })
      await flushPromises()
      finishCreate()
      await Promise.all([creating, deleting])
      await flushPromises()
      expect(ids()).toEqual([10, 11])
      expect(get('getCount')).toBe(2)
    }
  )

  test('processes events in a new view while creation in the old view remains pending', async () => {
    await startCreate()
    const staleDeletion = rowDeleted(existingRows[1])
    store.state.view.selected = { ...view, id: 2 }
    store.commit('page/view/grid/SET_LAST_GRID_ID', 2)
    store.commit('page/view/grid/CLEAR_ROWS')
    store.commit('page/view/grid/ADD_ROWS', {
      rows: existingRows.map((row) => populateRow({ ...row })),
      count: 2,
      bufferStartIndex: 0,
      bufferLimit: 2,
      prependToRows: 0,
      appendToRows: 2,
    })
    let processed = false
    const currentDeletion = rowDeleted(existingRows[0]).then(() => {
      processed = true
    })

    try {
      await vi.waitFor(() => expect(processed).toBe(true), { timeout: 500 })
      expect(ids()).toEqual([11])
      expect(get('getCount')).toBe(1)
    } finally {
      finishCreate()
      await Promise.all([creating, staleDeletion, currentDeletion])
    }
    expect(ids()).toEqual([11])
    expect(get('getCount')).toBe(1)
  })

  test('schedules every row in an update frame before a later deletion', async () => {
    await startCreate()
    const handlers = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => {
        handlers[name] = handler
      },
    })
    const context = {
      store,
      app: { $registry: { getAll: () => ({ grid: gridType }) } },
    }
    const updating = handlers.rows_updated(context, {
      table_id: 1,
      rows: [savedRow, { ...existingRows[1], field_1: 'Changed' }],
      rows_before_update: [savedRow, existingRows[1]],
      metadata: {},
      updated_field_ids: [],
    })
    const deleting = rowDeleted(existingRows[1])
    finishCreate()
    await Promise.all([creating, updating, deleting])
    await flushPromises()
    expect(ids()).toEqual([10, 99])
    expect(get('getCount')).toBe(2)
  })
})
