import gridStore from '@baserow/modules/database/store/view/grid'
import { TestApp } from '@baserow/test/helpers/testApp'
import {
  EqualViewFilterType,
  ContainsViewFilterType,
} from '@baserow/modules/database/viewFilters'
import { clone } from '@baserow/modules/core/utils/object'
import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'
import { getDefinedRowsFromSectionRows } from '@baserow/modules/database/utils/gridGroupBy'
import flushPromises from 'flush-promises'

import { createStore } from 'vuex'

const groupPathKey = (fieldId, value) =>
  pathKey({ [`field_${fieldId}`]: value }, [{ id: fieldId }])

describe('Grid view store', () => {
  let testApp = null
  let mockServer = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
    store = testApp.createStore({
      modules: {
        grid: gridStore,
      },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
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

    store.replaceState({ ...store.state, grid: state })

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

  test('sectioned group-by rows expose the same visible row index API', async () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 1 }],
      count: 3,
      fieldOptions: { 1: { hidden: false, order: 0 } },
      groupBy: {
        treeNodes: [
          { path: { field_1: 'A' }, depth: 0, row_count: 2 },
          { path: { field_1: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(1, 'A'),
      rows: [
        { id: 10, order: '1.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 11, order: '2.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(1, 'B'),
      rows: [
        { id: 12, order: '3.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })

    expect(store.getters['grid/getRowIndexById'](12)).toBe(2)
    expect(store.getters['grid/getRowIdByIndex'](1)).toBe(11)
    expect(store.getters['grid/getRow'](10).id).toBe(10)
    expect(store.getters['grid/getAllRows'].map((row) => row.id)).toEqual([
      10, 11, 12,
    ])

    await store.dispatch('grid/setMultipleSelect', {
      rowHeadIndex: 1,
      fieldHeadIndex: 0,
      rowTailIndex: 2,
      fieldTailIndex: 0,
    })

    expect(store.getters['grid/areMultiSelectRowsWithinBuffer']).toBe(true)
    expect(store.getters['grid/getSelectedRows'].map((row) => row.id)).toEqual([
      11, 12,
    ])

    await store.dispatch('grid/setSelectedCell', {
      rowId: 12,
      fieldId: 1,
      fields: [{ id: 1, primary: true }],
    })
    expect(store.getters['grid/getRow'](12)._.selected).toBe(true)

    // The vertical range follows the layout: header A (48) + two rows + add row
    // (3 * 33) + the sibling group gap (8) puts header B at 155 and row 12 at 203.
    const fields = [{ id: 1, primary: true }]
    expect(
      store.getters['grid/getGroupByRowVerticalRange'](10, fields)
    ).toEqual({ top: 48, bottom: 81 })
    expect(
      store.getters['grid/getGroupByRowVerticalRange'](12, fields)
    ).toEqual({ top: 203, bottom: 236 })
    expect(
      store.getters['grid/getGroupByRowVerticalRange'](999, fields)
    ).toBeNull()
  })

  // Regression safety net for the grouped-store refactor: flat mode and grouped
  // mode must expose an identical row read + index API for the same logical data.
  // Batch A (rowLocations as the authoritative index, sectionRows derived, the
  // shared CRUD helper) must keep every assertion below green.
  describe('flat vs grouped parity (read + index surface)', () => {
    // Flat order is [10, 11, 12, 13, 14]; grouped splits them into group A
    // (10, 11, 12) and group B (13, 14) yet exposes the same row indexes.
    const ROWS = [
      { id: 10, order: '1.00', field_1: 'A' },
      { id: 11, order: '2.00', field_1: 'A' },
      { id: 12, order: '3.00', field_1: 'A' },
      { id: 13, order: '4.00', field_1: 'B' },
      { id: 14, order: '5.00', field_1: 'B' },
    ]
    const withUiState = (row) => ({
      ...row,
      _: { selected: false, selectedFieldId: -1 },
    })

    const seedFlat = () => {
      const state = Object.assign(gridStore.state(), {
        count: ROWS.length,
        bufferStartIndex: 0,
        bufferLimit: 10,
        bufferRequestSize: 10,
        fieldOptions: { 1: { hidden: false, order: 0 } },
        rows: ROWS.map(withUiState),
      })
      store.replaceState({ ...store.state, grid: state })
    }

    const seedGrouped = () => {
      const state = Object.assign(gridStore.state(), {
        activeGroupBys: [{ field: 1 }],
        count: ROWS.length,
        fieldOptions: { 1: { hidden: false, order: 0 } },
        groupBy: {
          ...gridStore.state().groupBy,
          treeNodes: [
            { path: { field_1: 'A' }, depth: 0, row_count: 3 },
            { path: { field_1: 'B' }, depth: 0, row_count: 2 },
          ],
          collapse: { mode: 'expand', paths: [] },
          sectionRows: {},
          rowLocations: {},
        },
      })
      store.replaceState({ ...store.state, grid: state })
      store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
        sectionKey: groupPathKey(1, 'A'),
        rows: ROWS.slice(0, 3).map(withUiState),
        startPosition: 0,
      })
      store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
        sectionKey: groupPathKey(1, 'B'),
        rows: ROWS.slice(3).map(withUiState),
        startPosition: 0,
      })
    }

    test.each([
      ['flat', seedFlat],
      ['grouped', seedGrouped],
    ])('%s mode exposes the same row read + index API', (mode, seed) => {
      seed()

      // getAllRows preserves the logical order in both modes.
      expect(store.getters['grid/getAllRows'].map((row) => row.id)).toEqual([
        10, 11, 12, 13, 14,
      ])

      // getCount is the total row count in both modes.
      expect(store.getters['grid/getCount']).toBe(ROWS.length)

      // getRow resolves every row by id in both modes.
      for (const { id } of ROWS) {
        expect(store.getters['grid/getRow'](id).id).toBe(id)
      }

      // getRowIndexById and getRowIdByIndex round-trip identically in both modes.
      ROWS.forEach((row, index) => {
        expect(store.getters['grid/getRowIndexById'](row.id)).toBe(index)
        expect(store.getters['grid/getRowIdByIndex'](index)).toBe(row.id)
      })
    })
  })

  test('onRowChange marks an optimistic flat row as moved when it sorts elsewhere', async () => {
    const rowMetadata = {
      selected: true,
      selectedFieldId: 1,
      selectedBy: [1],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
    ]
    const row = {
      id: 99,
      order: '99.00',
      field_1: '',
      _: { ...rowMetadata },
    }
    const state = Object.assign(gridStore.state(), {
      rows: [
        {
          id: 1,
          order: '1.00',
          field_1: 'Row 020',
          _: { ...rowMetadata, selected: false, selectedBy: [] },
        },
        row,
      ],
      count: 2,
    })
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      filters_disabled: true,
      sortings: [{ field: 1, order: 'ASC', type: 'default' }],
      group_bys: [],
    }

    store.replaceState({ ...store.state, grid: state })

    await store.dispatch('grid/onRowChange', { view, row, fields })

    expect(row._.matchSortings).toBe(false)
  })

  test('createNewRows finalizes a selected sorted row with moved warning', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
    ]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const fetchByScrollTopDelayed = vi.fn()
    const sortedStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed,
            fetchAllFieldAggregationData: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      count: 2,
      bufferStartIndex: 0,
      bufferLimit: 2,
      rows: [
        {
          id: 1,
          order: '1.00',
          field_1: 'Row 001',
          _: { ...rowMetadata, persistentId: 'r1' },
        },
        {
          id: 2,
          order: '2.00',
          field_1: 'Row 002',
          _: { ...rowMetadata, persistentId: 'r2' },
        },
      ],
    })
    sortedStore.replaceState({ ...sortedStore.state, grid: state })

    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(200, {
      items: [{ id: 3, order: '3.00', field_1: '' }],
      metadata: { updated_field_ids: [] },
    })

    await sortedStore.dispatch('grid/createNewRows', {
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        filters_disabled: true,
        sortings: [{ field: 1, order: 'ASC', type: 'default' }],
        group_bys: [],
      },
      table: { id: 1 },
      fields,
      rows: [{}],
      selectPrimaryCell: true,
    })

    const finalizedRow = sortedStore.state.grid.rows.find((row) => row.id === 3)
    expect(finalizedRow).toBeDefined()
    expect(finalizedRow._.loading).toBe(false)
    expect(finalizedRow._.selected).toBe(true)
    expect(finalizedRow._.matchSortings).toBe(false)
    expect(fetchByScrollTopDelayed).not.toHaveBeenCalled()
  })

  test('updateRowValue queued behind a pending create targets the finalized row id', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
    ]
    const flatStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
            fetchAllFieldAggregationData: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      count: 0,
      bufferStartIndex: 0,
      bufferLimit: 10,
      rows: [],
    })
    flatStore.replaceState({ ...flatStore.state, grid: state })

    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      filters_disabled: true,
      sortings: [],
      group_bys: [],
    }

    // Hold the create POST so the edit queues behind it: the user types into the
    // pending row before the backend has assigned its real id.
    let finishCreate
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          finishCreate = () =>
            resolve([
              200,
              {
                items: [{ id: 99, order: '1.00', field_1: '' }],
                metadata: { updated_field_ids: [] },
              },
            ])
        })
    )

    let patchedId
    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply((config) => {
      patchedId = JSON.parse(config.data).items[0].id
      return [
        200,
        {
          items: [{ id: 99, field_1: '99' }],
          metadata: { updated_field_ids: [1] },
        },
      ]
    })

    const createPromise = flatStore.dispatch('grid/createNewRows', {
      view,
      table: { id: 1 },
      fields,
      rows: [{}],
      selectPrimaryCell: false,
    })
    await new Promise((resolve) => setTimeout(resolve))

    const pendingRow = flatStore.getters['grid/getAllRows'][0]
    expect(pendingRow).toBeDefined()
    expect(pendingRow.id).not.toBe(99)

    const editPromise = flatStore.dispatch('grid/updateRowValue', {
      table: { id: 1 },
      view,
      fields,
      row: pendingRow,
      field: fields[0],
      value: '99',
      oldValue: '',
    })
    await new Promise((resolve) => setTimeout(resolve))

    finishCreate()
    await Promise.all([createPromise, editPromise])

    // The PATCH must target the finalized backend id, not the stale temporary id,
    // so the typed value is actually saved (grid-view-test-plan 1.4.1).
    expect(patchedId).toBe(99)
    expect(flatStore.getters['grid/getAllRows'][0].field_1).toBe('99')
  })

  test('createNewRows keeps a sorted-mismatched row appended below the buffer in place with a move warning', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
    ]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const bufferRows = []
    for (let i = 21; i <= 50; i += 1) {
      bufferRows.push({
        id: i,
        order: `${i}.00`,
        field_1: `Row ${String(i).padStart(3, '0')}`,
        _: { ...rowMetadata, persistentId: `r${i}` },
      })
    }
    const flatStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
            fetchAllFieldAggregationData: vi.fn(),
            visibleByScrollTop: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      count: 50,
      bufferStartIndex: 20,
      bufferLimit: 30,
      bufferRequestSize: 100,
      rows: bufferRows,
    })
    flatStore.replaceState({ ...flatStore.state, grid: state })

    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      filters_disabled: true,
      sortings: [{ field: 1, order: 'ASC', type: 'default' }],
      group_bys: [],
    }

    let finishCreate
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          finishCreate = () =>
            resolve([
              200,
              {
                items: [{ id: 99, order: '51.00', field_1: '' }],
                metadata: { updated_field_ids: [] },
              },
            ])
        })
    )

    const createPromise = flatStore.dispatch('grid/createNewRows', {
      view,
      table: { id: 1 },
      fields,
      rows: [{}],
      selectPrimaryCell: true,
    })
    await new Promise((resolve) => setTimeout(resolve))

    // Optimistically: the row is appended at the buffer tail and immediately
    // flagged as mismatched (its sorted destination, an empty Name, is the top of
    // the list) so the "Row has moved" warning shows while it stays selected.
    const all = flatStore.getters['grid/getAllRows']
    const optimistic = all[all.length - 1]
    expect(optimistic._.matchSortings).toBe(false)
    expect(optimistic._.selected).toBe(true)

    finishCreate()
    await createPromise

    // After the create confirms, the kept-in-place row keeps its warning, stays
    // selected, and appears exactly once at the buffer tail (no duplicate between
    // its sorted destination and the position it was appended at).
    const afterAll = flatStore.getters['grid/getAllRows']
    const finalized = flatStore.getters['grid/getRow'](99)
    expect(finalized).toBeDefined()
    expect(finalized._.matchSortings).toBe(false)
    expect(finalized._.selected).toBe(true)
    expect(afterAll.filter((r) => r.id === 99)).toHaveLength(1)
    expect(afterAll[afterAll.length - 1].id).toBe(99)
  })

  test('group-by shift-click multi-select uses compact visible row indexes', async () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 1 }],
      count: 3,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
        3: { hidden: false, order: 2 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_1: 'A' }, depth: 0, row_count: 2 },
          { path: { field_1: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(1, 'A'),
      rows: [
        { id: 10, order: '1.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 11, order: '2.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(1, 'B'),
      rows: [
        { id: 12, order: '3.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })

    await store.dispatch('grid/multiSelectStart', {
      rowId: 10,
      fieldIndex: 1,
    })
    await store.dispatch('grid/multiSelectShiftClick', {
      rowId: 11,
      fieldIndex: 2,
    })

    expect(store.getters['grid/getMultiSelectRowIndexSorted']).toEqual([0, 1])
    expect(store.getters['grid/getMultiSelectFieldIndexSorted']).toEqual([1, 2])
    expect(store.getters['grid/getSelectedRows'].map((row) => row.id)).toEqual([
      10, 11,
    ])
  })

  test('sectioned group-by row insert and delete keep visible row indexes compact', () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 1 }],
      count: 3,
      fieldOptions: { 1: { hidden: false, order: 0 } },
      groupBy: {
        treeNodes: [
          { path: { field_1: 'A' }, depth: 0, row_count: 2 },
          { path: { field_1: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(1, 'A'),
      rows: [
        { id: 10, order: '1.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 11, order: '2.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(1, 'B'),
      rows: [
        { id: 12, order: '3.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })

    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_1: 'A' },
      fields: [{ id: 1 }],
      delta: 1,
    })
    store.commit('grid/INSERT_ROW_AT_LOCATION', {
      sectionKey: groupPathKey(1, 'A'),
      position: 1,
      row: {
        id: 99,
        order: '1.50',
        _: { selected: false, selectedFieldId: -1 },
      },
    })

    expect(store.getters['grid/getAllRows'].map((row) => row.id)).toEqual([
      10, 99, 11, 12,
    ])
    expect(store.getters['grid/getRowIndexById'](11)).toBe(2)
    expect(store.getters['grid/getRowIndexById'](12)).toBe(3)
    expect(store.getters['grid/getRowIdByIndex'](2)).toBe(11)
    expect(store.getters['grid/getRowIdByIndex'](3)).toBe(12)

    store.commit('grid/REMOVE_ROW_AT_LOCATION', {
      sectionKey: groupPathKey(1, 'A'),
      position: 1,
      rowId: 99,
    })
    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_1: 'A' },
      fields: [{ id: 1 }],
      delta: -1,
    })

    expect(store.getters['grid/getAllRows'].map((row) => row.id)).toEqual([
      10, 11, 12,
    ])
    expect(store.getters['grid/getRowIndexById'](11)).toBe(1)
    expect(store.getters['grid/getRowIndexById'](12)).toBe(2)
    expect(store.getters['grid/getRowIdByIndex'](1)).toBe(11)
    expect(store.getters['grid/getRowIdByIndex'](2)).toBe(12)
  })

  test('a same-section reposition invalidates the absolute-offset cache', () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 1 }],
      count: 3,
      fieldOptions: { 1: { hidden: false, order: 0 } },
      groupBy: {
        treeNodes: [{ path: { field_1: 'A' }, depth: 0, row_count: 3 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
        absoluteRows: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(1, 'A'),
      rows: [
        { id: 10, order: '1.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 11, order: '2.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 12, order: '3.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })
    // Seed the absolute-offset cache as a fetch would.
    store.commit('grid/SET_GROUP_BY_ABSOLUTE_ROWS', {
      0: { id: 10 },
      1: { id: 11 },
      2: { id: 12 },
    })
    expect(Object.keys(store.state.grid.groupBy.absoluteRows)).toHaveLength(3)

    // Move a row within the same section (no count change, so nothing else clears the
    // cache). The now-stale cache must be dropped so an evicted section re-fetches.
    store.commit('grid/REMOVE_ROW_AT_LOCATION', {
      sectionKey: groupPathKey(1, 'A'),
      position: 0,
      rowId: 10,
    })
    store.commit('grid/INSERT_ROW_AT_LOCATION', {
      sectionKey: groupPathKey(1, 'A'),
      position: 2,
      row: {
        id: 10,
        order: '1.00',
        _: { selected: false, selectedFieldId: -1 },
      },
    })

    expect(store.state.grid.groupBy.absoluteRows).toEqual({})
  })

  test('updatedExistingRow moves loaded rows between group-by sections', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 3,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
        {
          id: 11,
          order: '2.00',
          field_1: 'Bob',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r11' },
        },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 12,
          order: '3.00',
          field_1: 'Carol',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r12' },
        },
      ],
      startPosition: 0,
    })

    await store.dispatch('grid/updatedExistingRow', {
      view: {
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      row: store.getters['grid/getRow'](10),
      values: { field_2: 'B' },
    })

    expect(store.getters['grid/getAllRows'].map((row) => row.id)).toEqual([
      11, 10, 12,
    ])
    expect(store.getters['grid/getRowIndexById'](10)).toBe(1)
    expect(store.getters['grid/getRowIdByIndex'](1)).toBe(10)
    expect(store.getters['grid/getRow'](10).field_2).toBe('B')
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
      { path: { field_2: 'B' }, depth: 0, row_count: 2 },
    ])
  })

  test('updatedExistingRow keeps a selected group-by change in place with a warning', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 3,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
          _: {
            ...rowMetadata,
            persistentId: 'r10',
            selected: true,
            selectedFieldId: 2,
            selectedBy: [2],
          },
        },
        {
          id: 11,
          order: '2.00',
          field_1: 'Bob',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r11' },
        },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 12,
          order: '3.00',
          field_1: 'Carol',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r12' },
        },
      ],
      startPosition: 0,
    })

    await store.dispatch('grid/updatedExistingRow', {
      view: {
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      row: store.getters['grid/getRow'](10),
      values: { field_2: 'B' },
    })

    const editedRow = store.getters['grid/getRow'](10)
    expect(editedRow.field_2).toBe('B')
    expect(editedRow._.matchSortings).toBe(false)
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (row) => row.id
      )
    ).toEqual([10, 11])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')].map(
        (row) => row.id
      )
    ).toEqual([12])
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 2 },
      { path: { field_2: 'B' }, depth: 0, row_count: 1 },
    ])
  })

  test('updateRowValue keeps a selected single-select group-by edit in place', async () => {
    const optionA = { id: 101, value: 'A', color: 'blue' }
    const optionB = { id: 102, value: 'B', color: 'green' }
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      {
        id: 2,
        name: 'Team',
        type: 'single_select',
        select_options: [optionA, optionB],
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: optionA.id }, depth: 0, row_count: 1 },
          { path: { field_2: optionB.id }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, optionA.id),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: optionA,
          _: {
            ...rowMetadata,
            persistentId: 'r10',
            selected: true,
            selectedFieldId: 2,
            selectedBy: [2],
          },
        },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, optionB.id),
      rows: [
        {
          id: 11,
          order: '2.00',
          field_1: 'Bob',
          field_2: optionB,
          _: { ...rowMetadata, persistentId: 'r11' },
        },
      ],
      startPosition: 0,
    })
    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(200, {
      items: [{ id: 10, field_2: optionB }],
      metadata: { updated_field_ids: [2] },
    })

    await store.dispatch('grid/updateRowValue', {
      table: { id: 1 },
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: store.getters['grid/getRow'](10),
      field: fields[1],
      fields,
      value: optionB,
      oldValue: optionA,
    })

    // Editing a selected row's group-by value keeps it in place with a move
    // warning; the move and count transfer happen on deselect.
    const editedRow = store.getters['grid/getRow'](10)
    expect(editedRow.field_2).toEqual(optionB)
    expect(editedRow._.matchSortings).toBe(false)
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, optionA.id)].map(
        (row) => row.id
      )
    ).toEqual([10])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, optionB.id)].map(
        (row) => row.id
      )
    ).toEqual([11])
    const nodeA = store.state.grid.groupBy.treeNodes.find(
      (node) => node.path.field_2 === optionA.id
    )
    const nodeB = store.state.grid.groupBy.treeNodes.find(
      (node) => node.path.field_2 === optionB.id
    )
    expect(nodeA.row_count).toBe(1)
    expect(nodeB.row_count).toBe(1)
    expect(nodeB.display).toBeUndefined()
    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('updateRowValue spins affected group aggregations before an optimistic group move changes counts', async () => {
    const optionA = { id: 101, value: 'A', color: 'blue' }
    const optionB = { id: 102, value: 'B', color: 'green' }
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      {
        id: 2,
        name: 'Team',
        type: 'single_select',
        select_options: [optionA, optionB],
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    store = testApp.createStore({
      modules: {
        grid: gridStore,
        field: {
          namespaced: true,
          getters: { getAll: () => fields },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      fieldOptions: {
        1: {
          hidden: false,
          order: 0,
          aggregation_type: 'not_empty_count',
          aggregation_raw_type: 'empty_count',
        },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [
          {
            path: { field_2: optionA.id },
            depth: 0,
            row_count: 1,
            aggregations: { field_1: 1 },
          },
          {
            path: { field_2: optionB.id },
            depth: 0,
            row_count: 1,
            aggregations: { field_1: 0 },
          },
        ],
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, optionA.id),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: '',
          field_2: optionA,
          _: {
            ...rowMetadata,
            persistentId: 'r10',
          },
        },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, optionB.id),
      rows: [
        {
          id: 11,
          order: '2.00',
          field_1: 'Bob',
          field_2: optionB,
          _: { ...rowMetadata, persistentId: 'r11' },
        },
      ],
      startPosition: 0,
    })

    let finishUpdate
    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          finishUpdate = () =>
            resolve([
              200,
              {
                items: [{ id: 10, field_2: optionB }],
                metadata: { updated_field_ids: [2] },
              },
            ])
        })
    )
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(200, {
      pages: [
        {
          parent: {},
          groups: [
            {
              path: { field_2: optionB.id },
              depth: 0,
              row_count: 2,
              aggregations: { field_1: 1 },
            },
          ],
          offset: 0,
          limit: 40,
        },
      ],
      aggregations: { field_1: 1 },
    })

    const updatePromise = store.dispatch('grid/updateRowValue', {
      table: { id: 1 },
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: store.getters['grid/getRow'](10),
      field: fields[1],
      fields,
      value: optionB,
      oldValue: optionA,
    })
    await new Promise((resolve) => setTimeout(resolve))

    expect(store.state.grid.groupBy.treeNodes[0].row_count).toBe(0)
    expect(store.state.grid.groupBy.aggregationsLoadingPaths).toEqual([
      groupPathKey(2, optionA.id),
      groupPathKey(2, optionB.id),
    ])

    finishUpdate()
    await updatePromise
    await flushPromises()

    expect(store.state.grid.groupBy.aggregationsLoadingPaths).toEqual([])
  })

  test('refreshRow recomputes and clears group aggregation spinners after a deselect group move', async () => {
    const optionA = { id: 101, value: 'A', color: 'blue' }
    const optionB = { id: 102, value: 'B', color: 'green' }
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      {
        id: 2,
        name: 'Team',
        type: 'single_select',
        select_options: [optionA, optionB],
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    store = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
          },
        },
        field: {
          namespaced: true,
          getters: { getAll: () => fields },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      fieldOptions: {
        1: {
          hidden: false,
          order: 0,
          aggregation_type: 'not_empty_count',
          aggregation_raw_type: 'empty_count',
        },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [
          {
            path: { field_2: optionA.id },
            depth: 0,
            row_count: 1,
            aggregations: { field_1: 1 },
          },
          {
            path: { field_2: optionB.id },
            depth: 0,
            row_count: 1,
            aggregations: { field_1: 0 },
          },
        ],
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    // Row 10 still sits in group A's section, but while selected its value was
    // edited to B, so it no longer matches the sort and must move to group B once
    // it is deselected.
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, optionA.id),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: optionB,
          _: {
            ...rowMetadata,
            persistentId: 'r10',
            selectedBy: [2],
            matchSortings: false,
          },
        },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, optionB.id),
      rows: [
        {
          id: 11,
          order: '2.00',
          field_1: 'Bob',
          field_2: optionB,
          _: { ...rowMetadata, persistentId: 'r11' },
        },
      ],
      startPosition: 0,
    })

    let groupByDataRequests = 0
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(() => {
      groupByDataRequests += 1
      return [
        200,
        {
          pages: [
            {
              parent: {},
              groups: [
                {
                  path: { field_2: optionA.id },
                  depth: 0,
                  row_count: 0,
                  aggregations: { field_1: 0 },
                },
                {
                  path: { field_2: optionB.id },
                  depth: 0,
                  row_count: 2,
                  aggregations: { field_1: 1 },
                },
              ],
              offset: 0,
              limit: 40,
            },
          ],
          aggregations: { field_1: 1 },
        },
      ]
    })

    await store.dispatch('grid/removeRowSelectedBy', {
      grid: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: store.getters['grid/getRow'](10),
      field: fields[1],
      fields,
      getScrollTop: () => 0,
    })
    await flushPromises()

    // The deselect move marks the affected groups' aggregations loading; the
    // recompute request must land and clear the spinners instead of leaving them
    // stuck forever.
    expect(groupByDataRequests).toBe(1)
    expect(store.state.grid.groupBy.aggregationsLoadingPaths).toEqual([])
  })

  test('updateFieldOptionsOfField clears the aggregation spinner when the save request fails', async () => {
    const fields = [{ id: 1, name: 'Name', type: 'text', primary: true }]
    store = testApp.createStore({
      modules: {
        grid: gridStore,
        field: {
          namespaced: true,
          getters: { getAll: () => fields },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      fieldOptions: { 1: { hidden: false, order: 0 } },
    })
    store.replaceState({ ...store.state, grid: state })

    mockServer.mock.onPatch('/database/views/1/field-options/').reply(500)

    await expect(
      store.dispatch('grid/updateFieldOptionsOfField', {
        field: fields[0],
        values: {
          aggregation_type: 'empty_count',
          aggregation_raw_type: 'empty_count',
        },
        oldValues: { aggregation_type: '', aggregation_raw_type: '' },
        // Mirrors the grouped picker, which owns its own refresh.
        skipAggregationRefresh: true,
      })
    ).rejects.toBeTruthy()
    await flushPromises()

    // A failed save must stop the spinner too; the picker showed it optimistically.
    expect(store.state.grid.fieldAggregationData[1].loading).toBe(false)
  })

  test('updateRowValue keeps a modal-open edit in place with a filter warning', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
    ]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      count: 2,
      bufferStartIndex: 0,
      bufferLimit: 2,
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'match',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
        {
          id: 11,
          order: '2.00',
          field_1: 'match',
          _: { ...rowMetadata, persistentId: 'r11' },
        },
      ],
    })
    store.replaceState({ ...store.state, grid: state })

    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(200, {
      items: [{ id: 10, field_1: 'changed' }],
      metadata: { updated_field_ids: [1] },
    })

    await store.dispatch('grid/updateRowValue', {
      table: { id: 1 },
      view: {
        id: 1,
        filters: [
          {
            id: 1,
            view: 1,
            field: 1,
            type: 'equal',
            value: 'match',
            preload_values: {},
            group: null,
          },
        ],
        filter_groups: [],
        filter_type: 'AND',
        filters_disabled: false,
        sortings: [],
        group_bys: [],
      },
      row: store.getters['grid/getRow'](10),
      field: fields[0],
      fields,
      value: 'changed',
      oldValue: 'match',
      isRowOpenedInModal: (row) => row.id === 10,
    })

    // Editing a row open in the row edit modal so it stops matching the filters must
    // keep it in the buffer with a filter warning; hiding is deferred to modal close.
    const editedRow = store.getters['grid/getRow'](10)
    expect(editedRow).toBeDefined()
    expect(editedRow.field_1).toBe('changed')
    expect(editedRow._.matchFilters).toBe(false)
    expect(store.getters['grid/getCount']).toBe(2)
    expect(store.state.grid.rows.map((row) => row.id)).toEqual([10, 11])
  })

  test('updateRowValue keeps a selected edit in place when the target group is not loaded', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: true,
      selectedFieldId: 2,
      selectedBy: [2],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r10',
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 1,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 1,
            nodes: {
              0: {
                path: { field_2: 'A' },
                depth: 0,
                row_count: 1,
                sibling_index: 0,
                row_offset: 0,
              },
            },
          },
        },
        absoluteRows: {},
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
          _: rowMetadata,
        },
      ],
      startPosition: 0,
    })
    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(200, {
      items: [{ id: 10, field_2: 'B' }],
      metadata: { updated_field_ids: [2] },
    })

    await store.dispatch('grid/updateRowValue', {
      table: { id: 1 },
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: store.getters['grid/getRow'](10),
      field: fields[1],
      fields,
      value: 'B',
      oldValue: 'A',
    })

    // Per the contract, the selected edited row stays in its loaded group with a
    // move warning; no new group/header is created optimistically (that happens
    // on deselect).
    const editedRow = store.getters['grid/getRow'](10)
    expect(editedRow.field_2).toBe('B')
    expect(editedRow._.matchSortings).toBe(false)
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (row) => row.id
      )
    ).toEqual([10])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')]
    ).toBeUndefined()
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
    ])
    expect(store.state.grid.groupBy.pages[''].totalSiblingCount).toBe(1)
    expect(store.state.grid.groupBy.pages[''].nodes).toEqual({
      0: {
        path: { field_2: 'A' },
        depth: 0,
        row_count: 1,
        sibling_index: 0,
        row_offset: 0,
      },
    })
  })

  test('group-by count updates preserve the backend loaded group order', () => {
    const groupByFields = [{ id: 2, name: 'Category', type: 'text' }]
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      count: 4,
      groupBy: {
        treeNodes: [
          {
            path: { field_2: 'Research' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
          },
          {
            path: { field_2: 'Marketing' },
            depth: 0,
            row_count: 1,
            sibling_index: 1,
            row_offset: 2,
          },
          {
            path: { field_2: 'Development' },
            depth: 0,
            row_count: 1,
            sibling_index: 2,
            row_offset: 3,
          },
        ],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 3,
            nodes: {
              0: {
                path: { field_2: 'Research' },
                depth: 0,
                row_count: 2,
                sibling_index: 0,
                row_offset: 0,
              },
              1: {
                path: { field_2: 'Marketing' },
                depth: 0,
                row_count: 1,
                sibling_index: 1,
                row_offset: 2,
              },
              2: {
                path: { field_2: 'Development' },
                depth: 0,
                row_count: 1,
                sibling_index: 2,
                row_offset: 3,
              },
            },
          },
        },
        absoluteRows: {},
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_2: 'Development' },
      fields: groupByFields,
      delta: 1,
    })

    expect(
      store.state.grid.groupBy.treeNodes.map((node) => node.path.field_2)
    ).toEqual(['Research', 'Marketing', 'Development'])
    expect(
      Object.values(store.state.grid.groupBy.pages[''].nodes).map(
        (node) => node.path.field_2
      )
    ).toEqual(['Research', 'Marketing', 'Development'])
  })

  test('group-by count updates insert new single select groups using option order', () => {
    const options = [
      { id: 1, value: 'Research' },
      { id: 2, value: 'Marketing' },
      { id: 3, value: 'Development' },
      { id: 4, value: 'Design' },
    ]
    const categoryField = {
      id: 2,
      name: 'Category',
      type: 'single_select',
      select_options: options,
    }
    const groupByFields = [categoryField]
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'order' }],
      count: 16,
      groupBy: {
        treeNodes: [
          {
            path: { field_2: 1 },
            depth: 0,
            row_count: 4,
            sibling_index: 0,
            row_offset: 0,
          },
          {
            path: { field_2: 3 },
            depth: 0,
            row_count: 6,
            sibling_index: 1,
            row_offset: 4,
          },
          {
            path: { field_2: 4 },
            depth: 0,
            row_count: 6,
            sibling_index: 2,
            row_offset: 10,
          },
        ],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 3,
            nodes: {
              0: {
                path: { field_2: 1 },
                depth: 0,
                row_count: 4,
                sibling_index: 0,
                row_offset: 0,
              },
              1: {
                path: { field_2: 3 },
                depth: 0,
                row_count: 6,
                sibling_index: 1,
                row_offset: 4,
              },
              2: {
                path: { field_2: 4 },
                depth: 0,
                row_count: 6,
                sibling_index: 2,
                row_offset: 10,
              },
            },
          },
        },
        absoluteRows: {},
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_2: 2 },
      fields: groupByFields,
      delta: 1,
      registry: store.$registry,
    })

    const optionValue = (node) =>
      options.find((option) => option.id === node.path.field_2).value
    expect(store.state.grid.groupBy.treeNodes.map(optionValue)).toEqual([
      'Research',
      'Marketing',
      'Development',
      'Design',
    ])
    expect(
      Object.values(store.state.grid.groupBy.pages[''].nodes).map(optionValue)
    ).toEqual(['Research', 'Marketing', 'Development', 'Design'])
    expect(
      Object.values(store.state.grid.groupBy.pages[''].nodes).map(
        (node) => node.row_offset
      )
    ).toEqual([0, 4, 5, 11])
  })

  test('group-by count updates invalidate absolute rows before viewport hydration', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Category', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const row = (id, name, category) => ({
      id,
      order: `${id}.00`,
      field_1: name,
      field_2: category,
    })
    const researchA = row(1, 'Research A', 'Research')
    const researchB = row(2, 'Research B', 'Research')
    const developmentA = row(3, 'Development A', 'Development')
    const developmentB = row(4, 'Development B', 'Development')
    const movedToResearch = row(5, 'Moved to research', 'Research')
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 4,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [
          {
            path: { field_2: 'Research' },
            depth: 0,
            row_count: 2,
            sibling_index: 0,
            row_offset: 0,
          },
          {
            path: { field_2: 'Development' },
            depth: 0,
            row_count: 2,
            sibling_index: 1,
            row_offset: 2,
          },
        ],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 2,
            nodes: {
              0: {
                path: { field_2: 'Research' },
                depth: 0,
                row_count: 2,
                sibling_index: 0,
                row_offset: 0,
              },
              1: {
                path: { field_2: 'Development' },
                depth: 0,
                row_count: 2,
                sibling_index: 1,
                row_offset: 2,
              },
            },
          },
        },
        absoluteRows: {
          0: researchA,
          1: researchB,
          2: developmentA,
          3: developmentB,
        },
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'Research'),
      rows: [researchA, researchB],
      startPosition: 0,
    })

    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_2: 'Research' },
      fields: [fields[1]],
      delta: 1,
    })
    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_2: 'Development' },
      fields: [fields[1]],
      delta: -1,
    })

    let requestParams = null
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      requestParams = config.params
      return [
        200,
        {
          count: 4,
          results: [researchA, researchB, movedToResearch, developmentB],
        },
      ]
    })

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      scrollTop: 0,
    })

    expect(mockServer.mock.history.get).toHaveLength(1)
    expect(requestParams.get('offset')).toBe('0')
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'Research')].map(
        (row) => row.field_2
      )
    ).toEqual(['Research', 'Research', 'Research'])
  })

  test('first load fills the viewport in a single group-by data request', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
      { id: 3, name: 'Role', type: 'text' },
    ]
    const groupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 1,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        ...gridStore.state().groupBy,
        pages: {},
        treeNodes: [],
        collapse: { mode: 'expand', paths: [] },
      },
    })
    store.replaceState({ ...store.state, grid: state })

    const groupByDataRequests = []
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByDataRequests.push(config.params)
        return [
          200,
          {
            pages: [
              {
                parent: {},
                groups: [
                  {
                    path: { field_2: 'A' },
                    depth: 0,
                    row_count: 1,
                    children_count: 1,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 1,
              },
              {
                parent: { field_2: 'A' },
                groups: [
                  {
                    path: { field_2: 'A', field_3: 'Dev' },
                    depth: 1,
                    row_count: 1,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 1,
              },
            ],
          },
        ]
      })
    mockServer.mock.onGet('/database/views/grid/1/').reply(() => [
      200,
      {
        results: [
          {
            id: 10,
            order: '1.00',
            field_1: 'Alice',
            field_2: 'A',
            field_3: 'Dev',
          },
        ],
      },
    ])

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      scrollTop: 0,
    })

    // One request loads the whole visible tree; the per-depth loop finds nothing left
    // to fetch and breaks instead of waterfalling.
    expect(groupByDataRequests).toHaveLength(1)
    // The budget is the padded viewport in rows: 330px / 33px = 10.
    expect(groupByDataRequests[0].get('descendant_row_budget')).toBe('10')
    expect(groupByDataRequests[0].get('include_descendants')).toBe('true')
  })

  test('a scroll batches every visible parent into one group-by data request', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
      { id: 3, name: 'Role', type: 'text' },
    ]
    const groupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const topNode = (value, siblingIndex, rowOffset) => ({
      path: { field_2: value },
      depth: 0,
      row_count: 2,
      children_count: 1,
      sibling_index: siblingIndex,
      row_offset: rowOffset,
    })
    const nodes = [topNode('A', 0, 0), topNode('B', 1, 2), topNode('C', 2, 4)]
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 6,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 990,
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: nodes,
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 3,
            nodes: { 0: nodes[0], 1: nodes[1], 2: nodes[2] },
          },
        },
        collapse: { mode: 'expand', paths: [] },
        offsetsServerConfirmed: true,
      },
    })
    store.replaceState({ ...store.state, grid: state })

    const groupByDataRequests = []
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByDataRequests.push(config.params)
        return [
          200,
          {
            pages: ['A', 'B', 'C'].map((value) => ({
              parent: { field_2: value },
              groups: [
                {
                  path: { field_2: value, field_3: `${value}1` },
                  depth: 1,
                  row_count: 2,
                  sibling_index: 0,
                  row_offset: 0,
                },
              ],
              offset: 0,
              limit: 40,
              group_count: 1,
            })),
          },
        ]
      })
    mockServer.mock
      .onGet('/database/views/grid/1/')
      .reply(() => [200, { results: [] }])

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      scrollTop: 0,
    })

    // Every visible parent's children load in a single request rather than one
    // request per parent (or per depth level).
    expect(groupByDataRequests).toHaveLength(1)
    const parents = JSON.parse(groupByDataRequests[0].get('parents'))
    expect(parents.map((page) => page.parent.field_2)).toEqual(['A', 'B', 'C'])
    expect(groupByDataRequests[0].get('descendant_row_budget')).toBe('30')
  })

  test('add-row in a mid-scroll group keeps a sparse page from skeletoning', () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const node = (value, siblingIndex, rowOffset) => ({
      path: { field_2: value },
      depth: 0,
      row_count: 5,
      sibling_index: siblingIndex,
      row_offset: rowOffset,
    })
    // Two disjoint loaded windows (sibling 0..1 and 40..41), as left behind by scrolling
    // around a large collapsed grouping.
    const nodes = {
      0: node('Aa', 0, 0),
      1: node('Ab', 1, 5),
      40: node('Ma', 40, 200),
      41: node('Mc', 41, 205),
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 400,
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: Object.values(nodes).map((n) => ({ ...n })),
        pages: {
          '': { parentPath: {}, totalSiblingCount: 80, nodes },
        },
        collapse: { mode: 'collapse', paths: [], initialized: true },
      },
    })
    store.replaceState({ ...store.state, grid: state })

    // Optimistically add a row to the later-window group (sibling 40).
    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_2: 'Ma' },
      fields: [fields[1]],
      delta: 1,
    })

    // The later window keeps its real (sparse) keys instead of compacting to 0..3.
    const pageNodes = store.state.grid.groupBy.pages[''].nodes
    expect(
      Object.keys(pageNodes)
        .map(Number)
        .sort((a, b) => a - b)
    ).toEqual([0, 1, 40, 41])
    expect(pageNodes[40].row_count).toBe(6)

    // The mid-scroll window therefore renders as real headers, not a placeholder band.
    const layout = store.getters['grid/getGroupByLayout']
    const placeholderOverWindow = layout.items.filter(
      (item) =>
        item.type === 'groupPlaceholder' &&
        item.siblingStartIndex <= 40 &&
        item.siblingEndIndex > 40
    )
    expect(placeholderOverWindow).toHaveLength(0)
    expect(
      layout.items.some(
        (item) => item.type === 'header' && item.path?.field_2 === 'Ma'
      )
    ).toBe(true)
  })

  test('add-row creating a new group in a sparse page keeps it from skeletoning', () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const node = (value, siblingIndex, rowOffset) => ({
      path: { field_2: value },
      depth: 0,
      row_count: 5,
      sibling_index: siblingIndex,
      row_offset: rowOffset,
    })
    const nodes = {
      0: node('Aa', 0, 0),
      1: node('Ab', 1, 5),
      40: node('Ma', 40, 200),
      41: node('Mc', 41, 205),
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 400,
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: Object.values(nodes).map((n) => ({ ...n })),
        pages: {
          '': { parentPath: {}, totalSiblingCount: 80, nodes },
        },
        collapse: { mode: 'collapse', paths: [], initialized: true },
      },
    })
    store.replaceState({ ...store.state, grid: state })

    // Add a row that creates a brand-new group ('Mb') inside the later loaded window.
    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_2: 'Mb' },
      fields: [fields[1]],
      delta: 1,
      registry: store.$registry,
    })

    // The existing windows keep their real keys (Ma stays at 40, not compacted), and the
    // new group is slotted in beside them rather than densifying the page.
    const pageNodes = store.state.grid.groupBy.pages[''].nodes
    expect(pageNodes[40].path.field_2).toBe('Ma')
    expect(Object.keys(pageNodes)).toHaveLength(5)
    expect(store.state.grid.groupBy.pages[''].totalSiblingCount).toBe(81)

    const layout = store.getters['grid/getGroupByLayout']
    const placeholderOverWindow = layout.items.filter(
      (item) =>
        item.type === 'groupPlaceholder' &&
        item.siblingStartIndex <= 40 &&
        item.siblingEndIndex > 40
    )
    expect(placeholderOverWindow).toHaveLength(0)
  })

  test('createNewRows appends pasted rows to the matching group-by section in order', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 3,
      bufferStartIndex: 0,
      bufferLimit: 3,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 1 },
          { path: { field_2: 'B' }, depth: 0, row_count: 2 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Existing',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
      ],
      startPosition: 0,
    })

    const fetchByScrollTopDelayed = vi.spyOn(
      gridStore.actions,
      'fetchByScrollTopDelayed'
    )
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(200, {
      items: [
        {
          id: 11,
          order: '2.00',
          field_1: 'First pasted',
          field_2: 'B',
        },
        {
          id: 12,
          order: '3.00',
          field_1: 'Second pasted',
          field_2: 'B',
        },
      ],
      metadata: { updated_field_ids: [] },
    })

    await store.dispatch('grid/createNewRows', {
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      table: { id: 1 },
      fields,
      rows: [
        { field_1: 'First pasted', field_2: 'B' },
        { field_1: 'Second pasted', field_2: 'B' },
      ],
      skipFetchByScrollTop: true,
    })

    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')].map((row) => [
        row.id,
        row.field_1,
      ])
    ).toEqual([
      [10, 'Existing'],
      [11, 'First pasted'],
      [12, 'Second pasted'],
    ])
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
      { path: { field_2: 'B' }, depth: 0, row_count: 4 },
    ])
    expect(store.state.grid.count).toBe(5)
    expect(mockServer.mock.history.get).toHaveLength(0)
    expect(fetchByScrollTopDelayed).not.toHaveBeenCalled()
    fetchByScrollTopDelayed.mockRestore()
  })

  test('createNewRowInGroup does not show a moved warning for the optimistic row', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const fetchByScrollTopDelayed = vi.fn()
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed,
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 1 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Existing',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
      ],
      startPosition: 0,
    })

    let finishCreate
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          finishCreate = () =>
            resolve([
              200,
              {
                items: [
                  {
                    id: 11,
                    order: '2.00',
                    field_1: '',
                    field_2: 'B',
                  },
                ],
                metadata: { updated_field_ids: [] },
              },
            ])
        })
    )

    const createPromise = groupByStore.dispatch('grid/createNewRowInGroup', {
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      table: { id: 1 },
      fields,
      path: { field_2: 'B' },
      selectPrimaryCell: true,
    })
    await new Promise((resolve) => setTimeout(resolve))

    const optimisticRow =
      groupByStore.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')][1]
    expect(optimisticRow).toBeDefined()
    expect(optimisticRow._.matchSortings).toBe(true)

    finishCreate()
    await createPromise
    expect(fetchByScrollTopDelayed).not.toHaveBeenCalled()
    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('createNewRowInGroup with an empty path lands the row in its value-derived group', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const fetchByScrollTopDelayed = vi.fn()
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed,
            fetchAllFieldAggregationData: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 0,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(200, {
      items: [{ id: 11, order: '1.00', field_1: '', field_2: '' }],
      metadata: { updated_field_ids: [] },
    })

    // The empty-view add-row line passes the root path; the row must land in the
    // group derived from its own values, not in an unaddressable "" section.
    await groupByStore.dispatch('grid/createNewRowInGroup', {
      view: {
        id: 1,
        filters: [
          {
            id: 1,
            view: 1,
            field: 1,
            type: 'equal',
            value: 'nomatch',
            preload_values: {},
            group: null,
          },
        ],
        filter_groups: [],
        filter_type: 'AND',
        filters_disabled: false,
        sortings: [],
        group_bys: groupBys,
      },
      table: { id: 1 },
      fields,
      path: {},
      selectPrimaryCell: true,
    })

    const sectionKey = groupPathKey(2, '')
    const insertedRow =
      groupByStore.state.grid.groupBy.sectionRows[sectionKey]?.[0]
    expect(insertedRow).toBeDefined()
    expect(insertedRow._.matchFilters).toBe(false)
    expect(insertedRow._.selected).toBe(true)
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: '' }, depth: 0, row_count: 1 },
    ])
    expect(groupByStore.state.grid.count).toBe(1)
  })

  test('updateRowValue keeps a filtered-out selected group-by edit in its occupied group', async () => {
    const optionB = { id: 102, value: 'B', color: 'green' }
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Category',
        type: 'single_select',
        select_options: [optionB],
        _: { type: { type: 'single_select' } },
      },
      {
        id: 3,
        name: 'Completed',
        type: 'boolean',
        _: { type: { type: 'boolean' } },
      },
    ]
    const groupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const rowMetadata = {
      selected: true,
      selectedFieldId: 2,
      selectedBy: [2],
      loading: false,
      matchFilters: false,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r9',
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 1,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
        3: { hidden: false, order: 2 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: null }, depth: 0, row_count: 1 },
          { path: { field_2: null, field_3: false }, depth: 1, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })
    const emptySectionKey = pathKey({ field_2: null, field_3: false }, [
      { id: 2 },
      { id: 3 },
    ])
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: emptySectionKey,
      rows: [
        {
          id: 9,
          order: '1.00',
          field_1: '',
          field_2: null,
          field_3: false,
          _: { ...rowMetadata },
        },
      ],
      startPosition: 0,
    })

    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(200, {
      items: [{ id: 9, field_2: optionB }],
      metadata: { updated_field_ids: [2] },
    })

    await store.dispatch('grid/updateRowValue', {
      table: { id: 1 },
      view: {
        id: 1,
        filters: [
          {
            id: 1,
            view: 1,
            field: 1,
            type: 'equal',
            value: 'nomatch',
            preload_values: {},
            group: null,
          },
        ],
        filter_groups: [],
        filter_type: 'AND',
        filters_disabled: false,
        sortings: [],
        group_bys: groupBys,
      },
      row: store.getters['grid/getRow'](9),
      field: fields[1],
      fields,
      value: optionB,
      oldValue: null,
    })

    // The filtered-out selected row keeps both warnings in its occupied group;
    // deselect hides it from there instead of first moving it to a new group.
    const targetSectionKey = pathKey({ field_2: optionB.id, field_3: false }, [
      { id: 2 },
      { id: 3 },
    ])
    const row = store.getters['grid/getRow'](9)
    expect(row).toBeDefined()
    expect(row._.selected).toBe(true)
    expect(row._.matchFilters).toBe(false)
    expect(row._.matchSortings).toBe(false)
    expect(row.field_2).toEqual(optionB)
    expect(
      store.state.grid.groupBy.sectionRows[emptySectionKey].map((r) => r.id)
    ).toEqual([9])
    expect(
      store.state.grid.groupBy.sectionRows[targetSectionKey]
    ).toBeUndefined()
    const nodes = store.state.grid.groupBy.treeNodes.map((node) => ({
      path: node.path,
      row_count: node.row_count,
      display: node.display,
    }))
    expect(nodes).toEqual([
      { path: { field_2: null }, row_count: 1, display: undefined },
      {
        path: { field_2: null, field_3: false },
        row_count: 1,
        display: undefined,
      },
    ])
    expect(store.state.grid.count).toBe(1)
  })

  test('refreshRow hides a moved-warned row by decrementing its occupied group', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: false,
      matchSortings: false,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r9',
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 1,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [{ path: { field_2: '' }, depth: 0, row_count: 1 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })
    // The row was created in the "(empty)" group and its group-by value was then
    // edited while selected, so its values ("B") no longer match the section it
    // still occupies.
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, ''),
      rows: [
        {
          id: 9,
          order: '1.00',
          field_1: 'hidden by filter',
          field_2: 'B',
          _: { ...rowMetadata },
        },
      ],
      startPosition: 0,
    })

    await store.dispatch('grid/refreshRow', {
      grid: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: store.getters['grid/getRow'](9),
      fields,
    })

    // The occupied "(empty)" group is emptied; no phantom count remains and no
    // "B" group is invented by the removal.
    expect(store.getters['grid/getRow'](9)).toBeUndefined()
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: '' }, depth: 0, row_count: 0 },
    ])
    expect(store.state.grid.count).toBe(0)
  })

  test('createNewRowInGroup inserts before the supplied row', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const sectionKey = groupPathKey(2, 'B')
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
            fetchAllFieldAggregationData: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [{ path: { field_2: 'B' }, depth: 0, row_count: 2 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    const beforeRow = {
      id: 12,
      order: '2.00',
      field_1: 'Second',
      field_2: 'B',
      _: { ...rowMetadata, persistentId: 'r12' },
    }
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey,
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'First',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
        beforeRow,
      ],
      startPosition: 0,
    })

    let requestBefore = null
    let requestBody = null
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply((config) => {
      requestBefore = config.params.before
      requestBody = JSON.parse(config.data)
      return [
        200,
        {
          items: [
            {
              id: 11,
              order: '1.50',
              field_1: '',
              field_2: 'B',
            },
          ],
          metadata: { updated_field_ids: [] },
        },
      ]
    })

    await groupByStore.dispatch('grid/createNewRowInGroup', {
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      table: { id: 1 },
      fields,
      path: { field_2: 'B' },
      before: beforeRow,
      selectPrimaryCell: true,
    })

    expect(requestBefore).toBe(12)
    expect(requestBody.items[0].field_2).toBe('B')
    expect(
      groupByStore.state.grid.groupBy.sectionRows[sectionKey].map((row) => [
        row.id,
        row.field_1,
      ])
    ).toEqual([
      [10, 'First'],
      [11, ''],
      [12, 'Second'],
    ])
    expect(groupByStore.state.grid.groupBy.rowLocations).toEqual({
      10: { sectionKey, position: 0 },
      11: { sectionKey, position: 1 },
      12: { sectionKey, position: 2 },
    })
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'B' }, depth: 0, row_count: 3 },
    ])
  })

  test('createNewRowInGroup spins the affected group and footer aggregations until the backend confirms', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
          },
        },
        field: {
          namespaced: true,
          getters: { getAll: () => fields },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      fieldOptions: {
        1: {
          hidden: false,
          order: 0,
          aggregation_type: 'empty_count',
          aggregation_raw_type: 'empty_count',
        },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [
          {
            path: { field_2: 'A' },
            depth: 0,
            row_count: 1,
            aggregations: { field_1: 0 },
          },
          {
            path: { field_2: 'B' },
            depth: 0,
            row_count: 1,
            aggregations: { field_1: 0 },
          },
        ],
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    groupByStore.app = { $featureFlagIsEnabled: () => true }
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Existing',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
      ],
      startPosition: 0,
    })

    let finishCreate
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          finishCreate = () =>
            resolve([
              200,
              {
                items: [{ id: 11, order: '2.00', field_1: '', field_2: 'B' }],
                metadata: { updated_field_ids: [] },
              },
            ])
        })
    )
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(() => [
      200,
      {
        pages: [
          {
            parent: {},
            groups: [
              {
                path: { field_2: 'B' },
                depth: 0,
                aggregations: { field_1: 1 },
              },
            ],
            offset: 0,
            limit: 40,
          },
        ],
        aggregations: { field_1: 1 },
      },
    ])

    const createPromise = groupByStore.dispatch('grid/createNewRowInGroup', {
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      table: { id: 1 },
      fields,
      path: { field_2: 'B' },
      selectPrimaryCell: true,
    })
    await new Promise((resolve) => setTimeout(resolve))

    // While the create request is pending, the inserted group spins instead of
    // recomputing its aggregations from the optimistically bumped row count.
    expect(groupByStore.state.grid.groupBy.aggregationsLoadingPaths).toContain(
      groupPathKey(2, 'B')
    )
    // Sibling groups are untouched, so they must not spin.
    expect(
      groupByStore.state.grid.groupBy.aggregationsLoadingPaths
    ).not.toContain(groupPathKey(2, 'A'))

    // The table-level footer aggregation must spin too, otherwise it recomputes
    // `rowCount - value` from the bumped count and flashes a wrong value.
    expect(groupByStore.state.grid.fieldAggregationData[1].loading).toBe(true)

    finishCreate()
    await createPromise

    // The backend refresh delivered fresh values and cleared the spinner.
    expect(groupByStore.state.grid.groupBy.aggregationsLoadingPaths).toEqual([])
    expect(groupByStore.state.grid.fieldAggregationData[1].loading).toBe(false)
    expect(groupByStore.state.grid.fieldAggregationData[1].value).toBe(1)
  })

  test('deleteExistingRow spins the affected group and footer aggregations until the backend confirms', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
          },
        },
        field: {
          namespaced: true,
          getters: { getAll: () => fields },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      fieldOptions: {
        1: {
          hidden: false,
          order: 0,
          aggregation_type: 'empty_count',
          aggregation_raw_type: 'empty_count',
        },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [
          {
            path: { field_2: 'B' },
            depth: 0,
            row_count: 2,
            aggregations: { field_1: 0 },
          },
        ],
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    groupByStore.app = { $featureFlagIsEnabled: () => true }
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Existing',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
      ],
      startPosition: 0,
    })

    mockServer.mock.onDelete('/database/rows/table/1/10/').reply(200, {})
    let finishRefresh
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(
      () =>
        new Promise((resolve) => {
          finishRefresh = () =>
            resolve([
              200,
              {
                pages: [
                  {
                    parent: {},
                    groups: [
                      {
                        path: { field_2: 'B' },
                        depth: 0,
                        aggregations: { field_1: 1 },
                      },
                    ],
                    offset: 0,
                    limit: 40,
                  },
                ],
                aggregations: { field_1: 1 },
              },
            ])
        })
    )

    await groupByStore.dispatch('grid/deleteExistingRow', {
      table: { id: 1 },
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: {
        id: 10,
        order: '1.00',
        field_1: 'Existing',
        field_2: 'B',
        _: { ...rowMetadata, persistentId: 'r10' },
      },
      fields,
      getScrollTop: () => 0,
    })
    // Let the fire-and-forget aggregation refresh issue its request.
    await new Promise((resolve) => setTimeout(resolve))

    // The delete resolved but the aggregation refresh is still in flight, so the
    // group banner and the footer aggregation must spin (not recompute from the
    // decremented count) until it returns.
    expect(groupByStore.state.grid.groupBy.aggregationsLoadingPaths).toContain(
      groupPathKey(2, 'B')
    )
    expect(groupByStore.state.grid.fieldAggregationData[1].loading).toBe(true)

    finishRefresh()
    await new Promise((resolve) => setTimeout(resolve))

    expect(groupByStore.state.grid.groupBy.aggregationsLoadingPaths).toEqual([])
    expect(groupByStore.state.grid.fieldAggregationData[1].loading).toBe(false)
    expect(groupByStore.state.grid.fieldAggregationData[1].value).toBe(1)
  })

  test('createNewRowInGroup does not duplicate a queued edited row when adding another row', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Due date',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
            fetchAllFieldAggregationData: vi.fn(),
          },
        },
      },
    })
    const view = {
      id: 1,
      filters: [
        {
          id: 1,
          view: 1,
          field: 1,
          type: EqualViewFilterType.getType(),
          value: 'b',
        },
      ],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: groupBys,
    }
    const groupPath = { field_2: '1980-12-19' }
    const sectionKey = groupPathKey(2, groupPath.field_2)
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 1,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [{ path: groupPath, depth: 0, row_count: 1 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey,
      rows: [
        {
          id: 200021,
          order: '1.00',
          field_1: 'Before',
          field_2: groupPath.field_2,
          _: { ...rowMetadata, persistentId: 'r200021' },
        },
      ],
      startPosition: 0,
    })

    let postCount = 0
    let finishFirstCreate
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(() => {
      postCount += 1
      if (postCount === 1) {
        return new Promise((resolve) => {
          finishFirstCreate = () =>
            resolve([
              200,
              {
                items: [
                  {
                    id: 200022,
                    order: '2.00',
                    field_1: '',
                    field_2: groupPath.field_2,
                  },
                ],
                metadata: { updated_field_ids: [] },
              },
            ])
        })
      }

      return [
        200,
        {
          items: [
            {
              id: 200023,
              order: '3.00',
              field_1: '',
              field_2: groupPath.field_2,
            },
          ],
          metadata: { updated_field_ids: [] },
        },
      ]
    })
    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(200, {
      items: [{ id: 200022, field_1: 'b', field_2: groupPath.field_2 }],
      metadata: { updated_field_ids: [1] },
    })

    const createPromise = groupByStore.dispatch('grid/createNewRowInGroup', {
      view,
      table: { id: 1 },
      fields,
      path: groupPath,
      selectPrimaryCell: true,
    })
    await new Promise((resolve) => setTimeout(resolve))

    const pendingRow =
      groupByStore.state.grid.groupBy.sectionRows[sectionKey][1]
    expect(pendingRow).toBeDefined()
    expect(pendingRow._.matchFilters).toBe(false)

    const updatePromise = groupByStore.dispatch('grid/updateRowValue', {
      table: { id: 1 },
      view,
      fields,
      row: pendingRow,
      field: fields[0],
      value: 'b',
      oldValue: '',
    })
    await new Promise((resolve) => setTimeout(resolve))

    finishFirstCreate()
    await Promise.all([createPromise, updatePromise])

    await groupByStore.dispatch('grid/createNewRowInGroup', {
      view,
      table: { id: 1 },
      fields,
      path: groupPath,
      selectPrimaryCell: true,
    })

    expect(
      groupByStore.state.grid.groupBy.sectionRows[sectionKey].map((row) => [
        row.id,
        row.field_1,
      ])
    ).toEqual([
      [200021, 'Before'],
      [200022, 'b'],
      [200023, ''],
    ])
    expect(
      groupByStore.state.grid.groupBy.sectionRows[sectionKey].filter(
        (row) => row.id === 200022
      )
    ).toHaveLength(1)
    expect(groupByStore.state.grid.groupBy.rowLocations).toEqual({
      200021: { sectionKey, position: 0 },
      200022: { sectionKey, position: 1 },
      200023: { sectionKey, position: 2 },
    })
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: groupPath, depth: 0, row_count: 3 },
    ])
    expect(groupByStore.getters['grid/getCount']).toBe(3)
  })

  test('failed createNewRowInGroup keeps group count after optimistic row was already removed', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
            fetchAllFieldAggregationData: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 1,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
      ],
      startPosition: 0,
    })

    let failCreate
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(
      () =>
        new Promise((resolve) => {
          failCreate = () => resolve([500, { detail: 'Failed' }])
        })
    )

    const view = {
      id: 1,
      filters: [
        {
          id: 1,
          view: 1,
          field: 1,
          type: EqualViewFilterType.getType(),
          value: 'Alice',
        },
      ],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: groupBys,
    }

    const createPromise = groupByStore.dispatch('grid/createNewRowInGroup', {
      view,
      table: { id: 1 },
      fields,
      path: { field_2: 'A' },
      selectPrimaryCell: true,
    })
    await new Promise((resolve) => setTimeout(resolve))

    const optimisticRow =
      groupByStore.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')][1]
    expect(optimisticRow).toBeDefined()
    expect(optimisticRow._.matchFilters).toBe(false)
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 2 },
    ])

    await groupByStore.dispatch('grid/refreshRow', {
      grid: view,
      row: optimisticRow,
      fields,
    })
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
    ])

    failCreate()
    await expect(createPromise).rejects.toThrow()

    expect(
      groupByStore.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (row) => row.id
      )
    ).toEqual([10])
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
    ])
    expect(groupByStore.getters['grid/getCount']).toBe(1)
  })

  test('refreshRow repositions a moved row to its absolute position in a windowed section', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const sectionKey = groupPathKey(2, 'A')
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed: vi.fn(),
            fetchAllFieldAggregationData: vi.fn(),
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 103,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 103 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    // The loaded window starts deep into the group (absolute positions 100-102), as
    // happens after scrolling. Names are sorted ascending within the window.
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey,
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Banana',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
        {
          id: 11,
          order: '2.00',
          field_1: 'Date',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r11' },
        },
        {
          id: 12,
          order: '3.00',
          field_1: 'Fig',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r12' },
        },
      ],
      startPosition: 100,
    })
    expect(groupByStore.state.grid.groupBy.rowLocations).toEqual({
      10: { sectionKey, position: 100 },
      11: { sectionKey, position: 101 },
      12: { sectionKey, position: 102 },
    })

    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [{ field: 1, order: 'ASC', type: 'default' }],
      group_bys: groupBys,
    }

    // Edit the row at the top of the window so it should sort to the bottom, mirroring
    // the post-edit state (value changed, marked as moved, deselected).
    const movedRow = groupByStore.getters['grid/getRow'](10)
    groupByStore.commit('grid/UPDATE_ROW_VALUES', {
      row: movedRow,
      values: { field_1: 'Zucchini' },
    })
    groupByStore.commit('grid/SET_ROW_MATCH_SORTINGS', {
      row: movedRow,
      value: false,
    })

    await groupByStore.dispatch('grid/refreshRow', {
      grid: view,
      row: movedRow,
      fields,
    })

    // The moved row lands at its absolute position (102, after the removal reindexed the
    // other rows down to 100/101), not at a compacted index, and the section stays sorted.
    expect(groupByStore.state.grid.groupBy.rowLocations).toEqual({
      11: { sectionKey, position: 100 },
      12: { sectionKey, position: 101 },
      10: { sectionKey, position: 102 },
    })
    expect(
      getDefinedRowsFromSectionRows(
        groupByStore.state.grid.groupBy.sectionRows,
        sectionKey
      ).map((row) => [row.id, row.field_1])
    ).toEqual([
      [11, 'Date'],
      [12, 'Fig'],
      [10, 'Zucchini'],
    ])
    expect(groupByStore.getters['grid/getRow'](10)._.matchSortings).toBe(true)
  })

  test('updateDataIntoCells keeps pasted overflow row order in group-by mode', async () => {
    const fields = [
      {
        id: 1,
        name: 'Name',
        type: 'text',
        primary: true,
        _: { type: { type: 'text' } },
      },
      {
        id: 2,
        name: 'Team',
        type: 'text',
        _: { type: { type: 'text' } },
      },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const fetchByScrollTopDelayed = vi.fn()
    const pasteStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchByScrollTopDelayed,
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      bufferStartIndex: 0,
      bufferLimit: 2,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 1 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    pasteStore.replaceState({ ...pasteStore.state, grid: state })
    pasteStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 9,
          order: '1.00',
          field_1: 'Other',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r9' },
        },
      ],
      startPosition: 0,
    })
    pasteStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 10,
          order: '2.00',
          field_1: 'Target',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
      ],
      startPosition: 0,
    })

    mockServer.mock.onPatch('/database/rows/table/1/batch/').reply(200, {
      items: [
        {
          id: 10,
          order: '2.00',
          field_1: 'First pasted',
          field_2: 'B',
        },
      ],
      metadata: { updated_field_ids: [1, 2] },
    })
    mockServer.mock.onPost('/database/rows/table/1/batch/').reply(200, {
      items: [
        {
          id: 11,
          order: '3.00',
          field_1: 'Second pasted',
          field_2: 'B',
        },
      ],
      metadata: { updated_field_ids: [] },
    })

    await pasteStore.dispatch('grid/updateDataIntoCells', {
      table: { id: 1 },
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      allVisibleFields: fields,
      allFieldsInTable: fields,
      getScrollTop: () => 0,
      textData: [
        ['First pasted', 'B'],
        ['Second pasted', 'B'],
      ],
      rowIndex: 1,
      fieldIndex: 0,
    })

    expect(
      pasteStore.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')].map(
        (row) => [row.id, row.field_1]
      )
    ).toEqual([
      [10, 'First pasted'],
      [11, 'Second pasted'],
    ])
    expect(pasteStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
      { path: { field_2: 'B' }, depth: 0, row_count: 2 },
    ])
    expect(fetchByScrollTopDelayed).toHaveBeenCalledTimes(1)
    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('refreshRow removes grouped filter-mismatching rows and shrinks the group', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 3,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Keep one',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
        {
          id: 11,
          order: '2.00',
          field_1: 'Hidden',
          field_2: 'A',
          _: {
            ...rowMetadata,
            persistentId: 'r11',
            matchFilters: false,
          },
        },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        {
          id: 12,
          order: '3.00',
          field_1: 'Keep three',
          field_2: 'B',
          _: { ...rowMetadata, persistentId: 'r12' },
        },
      ],
      startPosition: 0,
    })

    await store.dispatch('grid/refreshRow', {
      grid: {
        filters: [
          {
            id: 1,
            view: 1,
            field: 1,
            type: ContainsViewFilterType.getType(),
            value: 'Keep',
          },
        ],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: store.getters['grid/getRow'](11),
      fields,
    })

    expect(store.getters['grid/getAllRows'].map((row) => row.id)).toEqual([
      10, 12,
    ])
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
      { path: { field_2: 'B' }, depth: 0, row_count: 1 },
    ])
    expect(store.getters['grid/getRowsLength']).toBe(2)
    expect(store.getters['grid/getCount']).toBe(2)
  })

  test('refreshRow ignores grouped rows that have already been removed', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const rowMetadata = {
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: 'r',
    }
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 1,
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })

    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
          _: { ...rowMetadata, persistentId: 'r10' },
        },
      ],
      startPosition: 0,
    })

    await store.dispatch('grid/refreshRow', {
      grid: {
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: {
        id: 'temporary-row',
        order: '2.00',
        field_1: '',
        field_2: 'A',
        _: {
          ...rowMetadata,
          persistentId: 'temporary-row',
          matchFilters: false,
        },
      },
      fields,
    })

    expect(store.getters['grid/getAllRows'].map((row) => row.id)).toEqual([10])
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
    ])
    expect(store.getters['grid/getCount']).toBe(1)
  })

  test('refresh enables group-by mode with one metadata request and one row request', async () => {
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
    }
    const groupByStore = testApp.createStore({
      modules: {
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            correctMultiSelect,
            fetchAllFieldAggregationData,
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: [],
      rowHeight: 33,
      windowHeight: 330,
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    let groupByRequestParams = null
    let rowRequestParams = null
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByRequestParams = config.params
        return [
          200,
          {
            pages: [
              {
                parent: {},
                groups: [
                  {
                    path: { field_2: 'A' },
                    depth: 0,
                    row_count: 1,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 1,
              },
            ],
          },
        ]
      })
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      rowRequestParams = config.params
      return [
        200,
        {
          count: 1,
          results: [
            {
              id: 10,
              order: '1.00',
              field_1: 'Alice',
              field_2: 'A',
            },
          ],
        },
      ]
    })

    await groupByStore.dispatch('grid/refresh', {
      view,
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.activeGroupBys).toEqual([
      { field: 2, order: 'ASC', type: 'default' },
    ])
    expect(groupByStore.state.grid.groupBy.collapse).toEqual({
      mode: 'expand',
      paths: [],
    })
    expect(mockServer.mock.history.get).toHaveLength(2)
    expect(groupByRequestParams.get('include_descendants')).toBe('true')
    expect(groupByRequestParams.get('include_totals')).toBe('true')
    expect(rowRequestParams.get('offset')).toBe('0')
    expect(rowRequestParams.get('limit')).toBe('40')
    expect(correctMultiSelect).toHaveBeenCalledOnce()
    // Grouped mode bundles footer totals into the group-by-data request, so the
    // standalone aggregation fetch is no longer dispatched.
    expect(fetchAllFieldAggregationData).not.toHaveBeenCalled()
  })

  test('fetchAllFieldAggregationData refreshes per-group values + footer totals in grouped mode', async () => {
    const baseState = gridStore.state()
    const state = Object.assign(baseState, {
      lastGridId: 1,
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      rowHeight: 33,
      windowHeight: 330,
      fieldOptions: {
        3: { aggregation_type: 'sum', aggregation_raw_type: 'sum' },
      },
      groupBy: {
        ...baseState.groupBy,
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, aggregations: { field_3: 10 } },
        ],
      },
    })
    const aggStore = testApp.createStore({
      modules: {
        grid: gridStore,
        field: {
          namespaced: true,
          getters: {
            getAll: () => [
              { id: 2, name: 'Team', type: 'text' },
              { id: 3, name: 'Amount', type: 'number' },
            ],
          },
        },
      },
    })
    aggStore.replaceState({ ...aggStore.state, grid: state })
    aggStore.app = { $featureFlagIsEnabled: () => true }

    let params = null
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        params = config.params
        return [
          200,
          {
            pages: [
              {
                parent: {},
                groups: [
                  {
                    path: { field_2: 'A' },
                    depth: 0,
                    row_count: 4,
                    aggregations: { field_3: 99 },
                  },
                ],
                offset: 0,
                limit: 40,
              },
            ],
            aggregations: { field_3: 99 },
          },
        ]
      })

    await aggStore.dispatch('grid/fetchAllFieldAggregationData', {
      view: { id: 1 },
    })

    // Consolidated: one group-by-data request carries group values + footer totals;
    // no standalone /aggregations/ call, and no spinner on a row-driven refresh.
    expect(params.get('aggregations_only')).toBe('true')
    expect(params.get('include_totals')).toBe('true')
    expect(aggStore.state.grid.groupBy.treeNodes[0].aggregations).toEqual({
      field_3: 99,
    })
    expect(aggStore.state.grid.groupBy.treeNodes[0].aggregation_row_count).toBe(
      4
    )
    expect(aggStore.getters['grid/getAllFieldAggregationData']).toEqual({
      3: { loading: false, value: 99 },
    })
    expect(aggStore.getters['grid/getGroupByAggregationsLoading']()).toBe(false)
  })

  test('un-hiding an aggregated field in grouped mode refetches its stale value', async () => {
    const baseState = gridStore.state()
    const state = Object.assign(baseState, {
      lastGridId: 1,
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      fieldOptions: {
        3: {
          hidden: true,
          aggregation_type: 'sum',
          aggregation_raw_type: 'sum',
        },
      },
      groupBy: {
        ...baseState.groupBy,
        // The field's value was dropped from the tree while it was hidden.
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, aggregations: {} }],
      },
    })
    const aggStore = testApp.createStore({
      modules: {
        grid: gridStore,
        field: {
          namespaced: true,
          getters: {
            getAll: () => [
              { id: 2, name: 'Team', type: 'text' },
              { id: 3, name: 'Amount', type: 'number' },
            ],
          },
        },
      },
    })
    aggStore.replaceState({ ...aggStore.state, grid: state })
    aggStore.app = { $featureFlagIsEnabled: () => true }

    mockServer.mock.onPatch('/database/views/1/field-options/').reply(200, {})
    let refreshed = false
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(() => {
      refreshed = true
      return [
        200,
        {
          pages: [
            {
              parent: {},
              groups: [
                {
                  path: { field_2: 'A' },
                  depth: 0,
                  row_count: 4,
                  aggregations: { field_3: 99 },
                },
              ],
              offset: 0,
              limit: 40,
            },
          ],
          aggregations: { field_3: 99 },
        },
      ]
    })

    await aggStore.dispatch('grid/updateFieldOptionsOfField', {
      field: { id: 3, name: 'Amount', type: 'number' },
      values: { hidden: false },
      oldValues: { hidden: true },
    })
    await new Promise((resolve) => setTimeout(resolve))
    await new Promise((resolve) => setTimeout(resolve))

    expect(refreshed).toBe(true)
    expect(aggStore.state.grid.groupBy.treeNodes[0].aggregations).toEqual({
      field_3: 99,
    })
  })

  test('a targeted fieldId spins that column while a grouped row-edit refresh runs', async () => {
    const baseState = gridStore.state()
    const state = Object.assign(baseState, {
      lastGridId: 1,
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      rowHeight: 33,
      windowHeight: 330,
      fieldOptions: {
        3: { aggregation_type: 'sum', aggregation_raw_type: 'sum' },
      },
      groupBy: {
        ...baseState.groupBy,
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, aggregations: { field_3: 10 } },
        ],
      },
    })
    const aggStore = testApp.createStore({
      modules: {
        grid: gridStore,
        field: {
          namespaced: true,
          getters: {
            getAll: () => [
              { id: 2, name: 'Team', type: 'text' },
              { id: 3, name: 'Amount', type: 'number' },
            ],
          },
        },
      },
    })
    aggStore.replaceState({ ...aggStore.state, grid: state })
    aggStore.app = { $featureFlagIsEnabled: () => true }

    let resolveRequest = null
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(
      () =>
        new Promise((resolve) => {
          resolveRequest = () =>
            resolve([
              200,
              {
                pages: [
                  {
                    parent: {},
                    groups: [
                      {
                        path: { field_2: 'A' },
                        depth: 0,
                        row_count: 4,
                        aggregations: { field_3: 99 },
                      },
                    ],
                    offset: 0,
                    limit: 40,
                  },
                ],
                aggregations: { field_3: 99 },
              },
            ])
        })
    )

    const promise = aggStore.dispatch('grid/fetchAllFieldAggregationData', {
      view: { id: 1 },
      fieldId: 3,
    })

    // The edited column spins mid-refresh, even though a row edit refreshes silently.
    expect(aggStore.getters['grid/getGroupByAggregationsLoading'](3)).toBe(true)

    await flushPromises()
    resolveRequest()
    await promise

    expect(aggStore.getters['grid/getGroupByAggregationsLoading'](3)).toBe(
      false
    )
    expect(aggStore.state.grid.groupBy.treeNodes[0].aggregations).toEqual({
      field_3: 99,
    })
    expect(aggStore.state.grid.groupBy.treeNodes[0].aggregation_row_count).toBe(
      4
    )
  })

  test('fetchAllFieldAggregationData makes no request in grouped mode when no aggregation is configured', async () => {
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      rowHeight: 33,
      windowHeight: 330,
    })
    const aggStore = testApp.createStore({
      modules: {
        grid: gridStore,
        field: { namespaced: true, getters: { getAll: () => [] } },
      },
    })
    aggStore.replaceState({ ...aggStore.state, grid: state })
    aggStore.app = { $featureFlagIsEnabled: () => true }

    let called = false
    mockServer.mock.onGet(/group-by-data|aggregations/).reply(() => {
      called = true
      return [200, { pages: [] }]
    })

    await aggStore.dispatch('grid/fetchAllFieldAggregationData', {
      view: { id: 1 },
    })

    expect(called).toBe(false)
  })

  test('refresh keeps the previous group-by state until the next grouping is ready', async () => {
    let resolveGroupByData = null
    let resolveRows = null
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const oldGroupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const nextGroupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: nextGroupBys,
    }
    const groupByStore = testApp.createStore({
      modules: {
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            correctMultiSelect,
            fetchAllFieldAggregationData,
          },
        },
      },
    })
    const oldGeneration = 12
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: oldGroupBys,
      count: 1,
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        pages: {
          '': {
            parentPath: {},
            nodes: {
              0: {
                path: { field_2: 'A' },
                depth: 0,
                row_count: 1,
                sibling_index: 0,
                row_offset: 0,
              },
            },
            totalSiblingCount: 1,
          },
        },
        absoluteRows: {
          0: {
            id: 10,
            order: '1.00',
            field_1: 'Alice',
            field_2: 'A',
            field_3: 'Dev',
          },
        },
        revision: 0,
        generation: oldGeneration,
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
        sectionRows: {
          [groupPathKey(2, 'A')]: [
            {
              id: 10,
              order: '1.00',
              field_1: 'Alice',
              field_2: 'A',
              field_3: 'Dev',
            },
          ],
        },
        rowLocations: {
          10: { sectionKey: groupPathKey(2, 'A'), position: 0 },
        },
      },
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(() => {
      return new Promise((resolve) => {
        resolveGroupByData = () =>
          resolve([
            200,
            {
              pages: [
                {
                  parent: {},
                  groups: [
                    {
                      path: { field_2: 'A' },
                      depth: 0,
                      row_count: 1,
                      children_count: 1,
                      sibling_index: 0,
                      row_offset: 0,
                    },
                  ],
                  offset: 0,
                  limit: 40,
                  group_count: 1,
                },
                {
                  parent: { field_2: 'A' },
                  groups: [
                    {
                      path: { field_2: 'A', field_3: 'Dev' },
                      depth: 1,
                      row_count: 1,
                      sibling_index: 0,
                      row_offset: 0,
                    },
                  ],
                  offset: 0,
                  limit: 40,
                  group_count: 1,
                },
              ],
            },
          ])
      })
    })
    mockServer.mock.onGet('/database/views/grid/1/').reply(() => {
      return new Promise((resolve) => {
        resolveRows = () =>
          resolve([
            200,
            {
              results: [
                {
                  id: 10,
                  order: '1.00',
                  field_1: 'Alice',
                  field_2: 'A',
                  field_3: 'Dev',
                },
              ],
            },
          ])
      })
    })

    const refreshPromise = groupByStore.dispatch('grid/refresh', {
      view,
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
        { id: 3, name: 'Role', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    await new Promise((resolve) => setTimeout(resolve))

    expect(groupByStore.state.grid.activeGroupBys).toEqual(oldGroupBys)
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
    ])
    expect(groupByStore.state.grid.groupBy.sectionRows).toEqual({
      [groupPathKey(2, 'A')]: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
          field_3: 'Dev',
        },
      ],
    })
    expect(groupByStore.state.grid.groupBy.generation).toBeGreaterThan(
      oldGeneration
    )

    resolveGroupByData()
    await new Promise((resolve) => setTimeout(resolve))

    expect(groupByStore.state.grid.activeGroupBys).toEqual(oldGroupBys)
    expect(groupByStore.state.grid.groupBy.sectionRows).toEqual({
      [groupPathKey(2, 'A')]: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
          field_3: 'Dev',
        },
      ],
    })

    resolveRows()
    await refreshPromise

    expect(groupByStore.state.grid.activeGroupBys).toEqual(nextGroupBys)
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      {
        path: { field_2: 'A' },
        depth: 0,
        row_count: 1,
        children_count: 1,
        sibling_index: 0,
        row_offset: 0,
      },
    ])
    expect(
      groupByStore.state.grid.groupBy.sectionRows[
        pathKey({ field_2: 'A', field_3: 'Dev' }, [{ id: 2 }, { id: 3 }])
      ].map((row) => row.id)
    ).toEqual([10])
    expect(mockServer.mock.history.get).toHaveLength(2)
    expect(correctMultiSelect).toHaveBeenCalledOnce()
    // Grouped mode bundles footer totals into the group-by-data request, so the
    // standalone aggregation fetch is no longer dispatched.
    expect(fetchAllFieldAggregationData).not.toHaveBeenCalled()
  })

  test('late group-by data responses from an older generation are ignored', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        ...gridStore.state().groupBy,
        generation: 4,
      },
    })
    store.replaceState({ ...store.state, grid: state })

    let resolveGroupByData = null
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(() => {
      return new Promise((resolve) => {
        resolveGroupByData = () =>
          resolve([
            200,
            {
              pages: [
                {
                  parent: {},
                  groups: [
                    {
                      path: { field_2: 'A' },
                      depth: 0,
                      row_count: 1,
                      sibling_index: 0,
                      row_offset: 0,
                    },
                  ],
                  offset: 0,
                  limit: 40,
                  group_count: 1,
                },
              ],
            },
          ])
      })
    })

    const request = store.dispatch('grid/fetchGroupByData', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      adhocFiltering: false,
    })
    await vi.waitFor(() => expect(resolveGroupByData).toBeTypeOf('function'))

    store.commit('grid/RESET_GROUP_BY_DATA')
    resolveGroupByData()
    await request

    expect(store.state.grid.groupBy.pages).toEqual({})
    expect(store.state.grid.groupBy.treeNodes).toEqual([])
  })

  test('late group-by row responses from an older generation are ignored', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 1,
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        collapse: { mode: 'expand', paths: [] },
        generation: 7,
      },
    })
    store.replaceState({ ...store.state, grid: state })

    let resolveRows = null
    mockServer.mock.onGet('/database/views/grid/1/').reply(() => {
      return new Promise((resolve) => {
        resolveRows = () =>
          resolve([
            200,
            {
              count: 1,
              results: [
                {
                  id: 10,
                  order: '1.00',
                  field_1: 'Alice',
                  field_2: 'A',
                },
              ],
            },
          ])
      })
    })

    const layout = store.getters['grid/getGroupByLayout']
    const request = store.dispatch('grid/fetchGroupByRowsForSections', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      sections: [
        {
          sectionKey: groupPathKey(2, 'A'),
          sectionPath: { field_2: 'A' },
          absoluteRowOffset: 0,
          rowCount: 1,
          startPosition: 0,
          endPosition: 1,
        },
      ],
      layout,
    })
    await vi.waitFor(() => expect(resolveRows).toBeTypeOf('function'))

    store.commit('grid/RESET_GROUP_BY_DATA')
    resolveRows()
    await request

    expect(store.state.grid.groupBy.absoluteRows).toEqual({})
    expect(store.state.grid.groupBy.sectionRows).toEqual({})
    expect(store.state.grid.groupBy.rowLocations).toEqual({})
  })

  test('toggleGroupCollapse applies the toggle optimistically and propagates a failed expand fetch', async () => {
    // Q7 contract: expanding a group toggles collapse state locally *before* the lazy
    // row fetch. If that fetch fails the error propagates (so the component surfaces it
    // via notifyIf) and the group stays expanded — unloaded pages retry on next scroll.
    const fetchGroupByRowsByScrollTop = vi
      .fn()
      .mockRejectedValue(new Error('network'))
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: { ...gridStore.actions, fetchGroupByRowsByScrollTop },
        },
      },
    })
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        // 'A' is the collapsed exception in expand mode, i.e. group 'A' is collapsed.
        collapse: { mode: 'expand', paths: [{ field_2: 'A' }] },
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: groupBys,
    }

    await expect(
      groupByStore.dispatch('grid/toggleGroupCollapse', {
        path: { field_2: 'A' },
        view,
        fields,
        adhocFiltering: false,
      })
    ).rejects.toThrow('network')

    // The toggle was applied before the fetch failed: 'A' is no longer collapsed.
    expect(groupByStore.state.grid.groupBy.collapse.paths).toEqual([])
  })

  test('setGroupByCollapseAll clamps grouped scrollTop after the layout shrinks', async () => {
    const fetchGroupByRowsByScrollTop = vi.fn().mockResolvedValue([])
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: { ...gridStore.actions, fetchGroupByRowsByScrollTop },
        },
      },
    })
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: groupBys,
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      scrollTop: 6000,
      windowHeight: 100,
      rowHeight: 33,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 100 },
          { path: { field_2: 'B' }, depth: 0, row_count: 100 },
          { path: { field_2: 'C' }, depth: 0, row_count: 100 },
        ],
        collapse: { mode: 'expand', paths: [] },
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    await groupByStore.dispatch('grid/setGroupByCollapseAll', {
      view,
      fields,
      collapse: true,
      adhocFiltering: false,
    })

    const maxCollapsedScrollTop =
      groupByStore.getters['grid/getGroupByLayout'].totalHeight -
      groupByStore.getters['grid/getWindowHeight']

    expect(groupByStore.state.grid.scrollTop).toBe(maxCollapsedScrollTop)
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ scrollTop: maxCollapsedScrollTop })
    )
    expect(
      groupByStore.getters['grid/getGroupByVisibleItems']([fields[1]]).some(
        (item) => item.type === 'header'
      )
    ).toBe(true)
  })

  test('refresh preserves group-by collapse state when already grouped', async () => {
    const fetchGroupByData = vi.fn()
    const fetchGroupByCount = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByData,
      fetchGroupByCount,
      fetchGroupByRowsByScrollTop,
      correctMultiSelect,
      fetchAllFieldAggregationData,
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: groupByActions,
        },
      },
    })
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const collapse = {
      mode: 'collapse',
      paths: [{ field_2: 'A' }],
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse,
        sectionRows: {},
        rowLocations: {},
      },
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    await groupByStore.dispatch('grid/refresh', {
      view: {
        id: 1,
        filters: [
          {
            id: 1,
            view: 1,
            field: 1,
            type: ContainsViewFilterType.getType(),
            value: 'A',
          },
        ],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [{ field: 1, order: 'ASC' }],
        group_bys: groupBys,
      },
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.groupBy.collapse).toEqual(collapse)
    expect(fetchGroupByData).toHaveBeenCalledOnce()
    expect(fetchGroupByCount).not.toHaveBeenCalled()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
  })

  test('sort-only refresh keeps grouped scroll position and refetches visible row offsets', async () => {
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [{ field: 1, order: 'DESC', type: 'default' }],
      group_bys: groupBys,
    }
    const groupByStore = testApp.createStore({
      modules: {
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            correctMultiSelect,
            fetchAllFieldAggregationData,
          },
        },
      },
    })
    const sectionKey = groupPathKey(2, 'B')
    const scrollTop = 104 + 1000 * 33
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 200002,
      rowHeight: 33,
      windowHeight: 330,
      scrollTop,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        ...gridStore.state().groupBy,
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2, row_offset: 0 },
          {
            path: { field_2: 'B' },
            depth: 0,
            row_count: 200000,
            row_offset: 2,
          },
        ],
        collapse: { mode: 'expand', paths: [{ field_2: 'A' }] },
        collapseInitialized: true,
      },
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })
    groupByStore.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey,
      startPosition: 984,
      rows: Array.from({ length: 42 }, (_, index) => ({
        id: 1000 + index,
        order: `${index}.00`,
        field_1: `Stale ${index}`,
        field_2: 'B',
      })),
    })

    const groupByDataRequests = []
    let rowRequestParams = null
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByDataRequests.push(config.params)
        return [
          200,
          {
            pages: [
              {
                parent: {},
                groups: [
                  {
                    path: { field_2: 'A' },
                    depth: 0,
                    row_count: 2,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                  {
                    path: { field_2: 'B' },
                    depth: 0,
                    row_count: 200000,
                    sibling_index: 1,
                    row_offset: 2,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 2,
              },
            ],
          },
        ]
      })
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      rowRequestParams = config.params
      const offset = Number(config.params.get('offset'))
      const limit = Number(config.params.get('limit'))
      return [
        200,
        {
          count: 200002,
          results: Array.from({ length: limit }, (_, index) => ({
            id: offset + index,
            order: `${offset + index}.00`,
            field_1: `Sorted ${offset + index}`,
            field_2: 'B',
          })),
        },
      ]
    })

    await groupByStore.dispatch('grid/refresh', {
      view,
      fields,
      adhocFiltering: false,
      adhocSorting: false,
      sourceEvent: 'sort',
    })

    expect(groupByStore.state.grid.scrollTop).toBe(scrollTop)
    expect(groupByDataRequests).toHaveLength(0)
    expect(rowRequestParams.get('offset')).toBe('920')
    expect(rowRequestParams.get('limit')).toBe('160')
    expect(
      groupByStore.state.grid.groupBy.sectionRows[sectionKey][984].field_1
    ).toBe('Sorted 986')
    expect(correctMultiSelect).toHaveBeenCalledOnce()
    expect(fetchAllFieldAggregationData).not.toHaveBeenCalled()
  })

  test('refresh resets a mixed group-by collapse to expand-all when adding a level', async () => {
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const initialGroupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const nextGroupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: nextGroupBys,
    }
    const groupByStore = testApp.createStore({
      modules: {
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            correctMultiSelect,
            fetchAllFieldAggregationData,
          },
        },
      },
    })
    const collapse = {
      mode: 'collapse',
      paths: [{ field_2: 'A' }],
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: initialGroupBys,
      rowHeight: 33,
      windowHeight: 330,
      scrollTop: 99999,
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse,
        sectionRows: {},
        rowLocations: {},
      },
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(200, {
      pages: [
        {
          parent: {},
          groups: [
            {
              path: { field_2: 'A' },
              depth: 0,
              row_count: 2,
              children_count: 2,
              sibling_index: 0,
              row_offset: 0,
            },
            {
              path: { field_2: 'B' },
              depth: 0,
              row_count: 1,
              children_count: 1,
              sibling_index: 1,
              row_offset: 2,
            },
          ],
          offset: 0,
          limit: 40,
          group_count: 2,
        },
      ],
    })
    // Resetting to expand-all fetches the first rows page in parallel with the skeleton.
    mockServer.mock.onGet('/database/views/grid/1/').reply(200, {
      count: 0,
      results: [],
    })

    await groupByStore.dispatch('grid/refresh', {
      view,
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
        { id: 3, name: 'Role', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    // A per-group (mixed) collapse can't be expressed by the multi-level fetch, so adding
    // a level resets it to expand-all rather than preserving it (which left the expanded
    // branches without their rows).
    expect(groupByStore.state.grid.activeGroupBys).toEqual(nextGroupBys)
    expect(groupByStore.state.grid.groupBy.collapse).toEqual({
      mode: 'expand',
      paths: [],
    })
    // The rebuilt layout invalidates the old scroll offset, so it restarts at the top
    // (otherwise the viewport would sit on an unloaded region and render blank).
    expect(groupByStore.state.grid.scrollTop).toBe(0)
    expect(correctMultiSelect).toHaveBeenCalledOnce()
    // Grouped mode bundles footer totals into the group-by-data request, so the
    // standalone aggregation fetch is no longer dispatched.
    expect(fetchAllFieldAggregationData).not.toHaveBeenCalled()
  })

  test('refresh preserves group-by collapse state when removing a group-by', async () => {
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const initialGroupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const nextGroupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: nextGroupBys,
    }
    const groupByStore = testApp.createStore({
      modules: {
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            correctMultiSelect,
            fetchAllFieldAggregationData,
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: initialGroupBys,
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          {
            path: { field_2: 'A', field_3: 'Developer' },
            depth: 1,
            row_count: 1,
          },
          {
            path: { field_2: 'A', field_3: 'Designer' },
            depth: 1,
            row_count: 1,
          },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
          {
            path: { field_2: 'B', field_3: 'Developer' },
            depth: 1,
            row_count: 1,
          },
        ],
        truncated: false,
        collapse: {
          mode: 'expand',
          paths: [
            { field_2: 'A', field_3: 'Developer' },
            { field_2: 'A', field_3: 'Designer' },
            { field_2: 'B', field_3: 'Developer' },
          ],
        },
        sectionRows: {},
        rowLocations: {},
      },
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(200, {
      pages: [
        {
          parent: {},
          groups: [
            {
              path: { field_2: 'A' },
              depth: 0,
              row_count: 2,
              sibling_index: 0,
              row_offset: 0,
            },
            {
              path: { field_2: 'B' },
              depth: 0,
              row_count: 1,
              sibling_index: 1,
              row_offset: 2,
            },
          ],
          offset: 0,
          limit: 40,
          group_count: 2,
        },
      ],
    })

    await groupByStore.dispatch('grid/refresh', {
      view,
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
        { id: 3, name: 'Role', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.activeGroupBys).toEqual(nextGroupBys)
    expect(groupByStore.state.grid.groupBy.collapse).toEqual({
      mode: 'expand',
      paths: [{ field_2: 'A' }, { field_2: 'B' }],
    })
    expect(mockServer.mock.history.get).toHaveLength(1)
    expect(correctMultiSelect).toHaveBeenCalledOnce()
    // Grouped mode bundles footer totals into the group-by-data request, so the
    // standalone aggregation fetch is no longer dispatched.
    expect(fetchAllFieldAggregationData).not.toHaveBeenCalled()
  })

  test('group-by scroll fetch aborts the previous in-flight scroll request', async () => {
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
    }
    const pendingRequests = []
    const fetchGroupByRowsByScrollTop = vi.fn((context, payload) => {
      return new Promise((resolve) => {
        pendingRequests.push({ payload, resolve })
      })
    })
    const groupByStore = testApp.createStore({
      modules: {
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            fetchGroupByRowsByScrollTop,
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: view.group_bys,
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    const firstRequest = groupByStore.dispatch('grid/fetchByScrollTop', {
      scrollTop: 100,
      fields: [{ id: 2, name: 'Team', type: 'text' }],
    })
    await Promise.resolve()

    const secondRequest = groupByStore.dispatch('grid/fetchByScrollTop', {
      scrollTop: 200,
      fields: [{ id: 2, name: 'Team', type: 'text' }],
    })
    await Promise.resolve()

    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledTimes(2)
    expect(pendingRequests[0].payload.signal.aborted).toBe(true)
    expect(pendingRequests[1].payload.signal.aborted).toBe(false)

    pendingRequests[0].resolve([])
    pendingRequests[1].resolve([])
    await Promise.all([firstRequest, secondRequest])
  })

  test('refresh preserves initialized group-by collapse state when re-enabling group-by', async () => {
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: groupBys,
    }
    const groupByStore = testApp.createStore({
      modules: {
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
        grid: {
          ...gridStore,
          actions: {
            ...gridStore.actions,
            correctMultiSelect,
            fetchAllFieldAggregationData,
          },
        },
      },
    })
    const collapse = {
      mode: 'collapse',
      paths: [{ field_2: 'A' }],
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: [],
      rowHeight: 33,
      windowHeight: 330,
      groupBy: {
        treeNodes: [],
        truncated: false,
        collapse,
        collapseInitialized: true,
        sectionRows: {},
        rowLocations: {},
      },
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(200, {
      pages: [
        {
          parent: {},
          groups: [
            {
              path: { field_2: 'A' },
              depth: 0,
              row_count: 1,
              sibling_index: 0,
              row_offset: 0,
            },
          ],
          offset: 0,
          limit: 40,
          group_count: 1,
        },
      ],
    })
    mockServer.mock.onGet('/database/views/grid/1/').reply(200, {
      count: 1,
      results: [
        {
          id: 10,
          order: '1.00',
          field_1: 'Alice',
          field_2: 'A',
        },
      ],
    })

    await groupByStore.dispatch('grid/refresh', {
      view,
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.activeGroupBys).toEqual(groupBys)
    expect(groupByStore.state.grid.groupBy.collapse).toEqual(collapse)
    expect(mockServer.mock.history.get).toHaveLength(2)
    expect(correctMultiSelect).toHaveBeenCalledOnce()
    // Grouped mode bundles footer totals into the group-by-data request, so the
    // standalone aggregation fetch is no longer dispatched.
    expect(fetchAllFieldAggregationData).not.toHaveBeenCalled()
  })

  test('fetchInitial uses group-by mode after syncing active group-bys', async () => {
    const fetchGroupByData = vi.fn()
    const fetchGroupByCount = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const updateSearch = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByData,
      fetchGroupByCount,
      fetchGroupByRowsByScrollTop,
      updateSearch,
    }
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: {
          ...gridStore,
          actions: groupByActions,
        },
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      rowHeight: 33,
      windowHeight: 330,
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    mockServer.mock.onGet('/database/views/grid/1/').reply(200, {
      count: 0,
      results: [],
    })

    await groupByStore.dispatch('grid/fetchInitial', {
      gridId: 1,
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.activeGroupBys).toEqual([
      { field: 2, order: 'ASC', type: 'default' },
    ])
    expect(groupByStore.state.grid.groupBy.collapse).toEqual({
      mode: 'expand',
      paths: [],
    })
    expect(fetchGroupByData).toHaveBeenCalledOnce()
    expect(fetchGroupByCount).not.toHaveBeenCalled()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
    expect(updateSearch).toHaveBeenCalledOnce()
    // The skeleton and the first rows page are both fetched through the mocked
    // group-by actions, so fetchInitial itself issues no direct rows request.
    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('fetchInitial keeps field options when group-by loads expanded', async () => {
    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
    }
    const groupByStore = testApp.createStore({
      modules: {
        grid: gridStore,
        view: {
          namespaced: true,
          getters: {
            get: () => () => view,
          },
        },
      },
    })
    const state = Object.assign(gridStore.state(), {
      rowHeight: 33,
      windowHeight: 330,
    })
    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    let groupByDataRequestParams = null
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByDataRequestParams = config.params
        return [
          200,
          {
            pages: [
              {
                parent: {},
                groups: [
                  {
                    path: { field_2: 'A' },
                    depth: 0,
                    row_count: 2,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                  {
                    path: { field_2: 'B' },
                    depth: 0,
                    row_count: 1,
                    sibling_index: 1,
                    row_offset: 2,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 2,
              },
            ],
          },
        ]
      })

    let countRequestParams = null
    let rowRequestParams = null
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      if (config.params.get('limit') === '0') {
        countRequestParams = config.params
      } else {
        rowRequestParams = config.params
      }
      return [
        200,
        {
          count: 3,
          results: [],
          field_options: {
            1: { hidden: false, order: 0 },
            2: { hidden: false, order: 1 },
          },
        },
      ]
    })

    await groupByStore.dispatch('grid/fetchInitial', {
      gridId: 1,
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByDataRequestParams.get('include_descendants')).toBe('true')
    // The first load carries the viewport's row budget so the descent fills the screen
    // in this single request: (windowHeight 330 + 2 * padding 16 * 33) / 33 = 42.
    expect(groupByDataRequestParams.get('descendant_row_budget')).toBe('42')
    expect(countRequestParams).toBe(null)
    expect(rowRequestParams.get('include')).toBe('field_options,row_metadata')
    expect(rowRequestParams.get('limit')).toBe('3')
    expect(groupByStore.state.grid.fieldOptions).toEqual({
      1: { hidden: false, order: 0 },
      2: { hidden: false, order: 1 },
    })
    expect(groupByStore.state.grid.count).toBe(3)
    expect(groupByStore.state.grid.groupBy.sectionRows).toEqual({})
  })

  test('group-by data fetch preserves existing row count', async () => {
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(200, {
      pages: [
        {
          parent: {},
          groups: [
            {
              path: { field_2: 'A' },
              depth: 0,
              row_count: 2,
              sibling_index: 0,
              row_offset: 0,
            },
            {
              path: { field_2: 'B' },
              depth: 0,
              row_count: 3,
              sibling_index: 1,
              row_offset: 2,
            },
          ],
          offset: 0,
          limit: 40,
          group_count: 2,
        },
      ],
    })
    store.state.grid.count = 123

    await store.dispatch('grid/fetchGroupByData', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
      },
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      adhocFiltering: false,
    })

    expect(store.state.grid.count).toBe(123)
  })

  test('group-by data fetch batches multiple parent pages', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
      { id: 3, name: 'Status', type: 'text' },
    ]
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [
        { field: 2, order: 'ASC', type: 'default' },
        { field: 3, order: 'ASC', type: 'default' },
      ],
    })
    store.replaceState({ ...store.state, grid: state })

    let requestParams = null
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        requestParams = config.params
        return [
          200,
          {
            pages: [
              {
                parent: { field_2: 'A' },
                groups: [
                  {
                    path: { field_2: 'A', field_3: 'Todo' },
                    depth: 1,
                    row_count: 2,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                ],
                offset: 0,
                limit: 1,
                group_count: 1,
              },
              {
                parent: { field_2: 'B' },
                groups: [
                  {
                    path: { field_2: 'B', field_3: 'Done' },
                    depth: 1,
                    row_count: 1,
                    sibling_index: 1,
                    row_offset: 3,
                  },
                ],
                offset: 1,
                limit: 10,
                group_count: 2,
              },
            ],
          },
        ]
      })

    await store.dispatch('grid/fetchGroupByData', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        group_bys: [
          { field: 2, order: 'ASC', type: 'default' },
          { field: 3, order: 'ASC', type: 'default' },
        ],
      },
      fields,
      adhocFiltering: false,
      parentRequests: [
        { parentPath: { field_2: 'A' }, offset: 0, limit: 40 },
        { parentPath: { field_2: 'B' }, offset: 1, limit: 10 },
      ],
      includeDescendants: true,
      descendantLimit: 7,
    })

    expect(mockServer.mock.history.get).toHaveLength(1)
    expect(JSON.parse(requestParams.get('parents'))).toEqual([
      { parent: { field_2: 'A' }, offset: 0, limit: 40 },
      { parent: { field_2: 'B' }, offset: 1, limit: 10 },
    ])
    expect(requestParams.get('include_descendants')).toBe('true')
    expect(requestParams.get('descendant_limit')).toBe('7')
    expect(
      store.state.grid.groupBy.pages[groupPathKey(2, 'A')].nodes[0].path
    ).toEqual({
      field_2: 'A',
      field_3: 'Todo',
    })
    expect(
      store.state.grid.groupBy.pages[groupPathKey(2, 'B')].nodes[1].path
    ).toEqual({
      field_2: 'B',
      field_3: 'Done',
    })
  })

  test('empty expanded group-by viewport fetch preloads descendants in one metadata request', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
      { id: 3, name: 'Status', type: 'text' },
    ]
    const groupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      bufferRequestSize: 4,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        ...gridStore.state().groupBy,
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
      },
    })
    store.replaceState({ ...store.state, grid: state })

    let groupByRequestParams = null
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByRequestParams = config.params
        return [
          200,
          {
            pages: [
              {
                parent: {},
                groups: [
                  {
                    path: { field_2: 'A' },
                    depth: 0,
                    row_count: 2,
                    children_count: 2,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                  {
                    path: { field_2: 'B' },
                    depth: 0,
                    row_count: 2,
                    children_count: 1,
                    sibling_index: 1,
                    row_offset: 2,
                  },
                ],
                offset: 0,
                limit: 4,
                group_count: 2,
              },
              {
                parent: { field_2: 'A' },
                groups: [
                  {
                    path: { field_2: 'A', field_3: 'Done' },
                    depth: 1,
                    row_count: 1,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                  {
                    path: { field_2: 'A', field_3: 'Todo' },
                    depth: 1,
                    row_count: 1,
                    sibling_index: 1,
                    row_offset: 1,
                  },
                ],
                offset: 0,
                limit: 4,
                group_count: 2,
              },
              {
                parent: { field_2: 'B' },
                groups: [
                  {
                    path: { field_2: 'B', field_3: 'Done' },
                    depth: 1,
                    row_count: 2,
                    sibling_index: 0,
                    row_offset: 2,
                  },
                ],
                offset: 0,
                limit: 4,
                group_count: 1,
              },
            ],
          },
        ]
      })

    let rowsRequestParams = null
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      rowsRequestParams = config.params
      return [
        200,
        {
          count: 4,
          results: [
            { id: 10, order: '1.00', field_1: 'Alice', field_2: 'A' },
            { id: 11, order: '2.00', field_1: 'Ada', field_2: 'A' },
            { id: 12, order: '3.00', field_1: 'Bob', field_2: 'B' },
            { id: 13, order: '4.00', field_1: 'Bea', field_2: 'B' },
          ],
        },
      ]
    })

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      scrollTop: 0,
    })

    expect(mockServer.mock.history.get).toHaveLength(2)
    expect(groupByRequestParams.get('include_descendants')).toBe('true')
    expect(groupByRequestParams.get('descendant_limit')).toBe('4')
    expect(groupByRequestParams.get('depth')).toBe(null)
    expect(rowsRequestParams.get('offset')).toBe('0')
    expect(rowsRequestParams.get('limit')).toBe('2')
  })

  test('group-by expanded viewport fetch loads children per parent, never by depth', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
      { id: 3, name: 'Status', type: 'text' },
    ]
    const groupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 4,
      bufferRequestSize: 2,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 3,
            nodes: {
              0: {
                path: { field_2: 'A' },
                depth: 0,
                row_count: 2,
                children_count: 1,
                sibling_index: 0,
                row_offset: 0,
              },
              1: {
                path: { field_2: 'B' },
                depth: 0,
                row_count: 1,
                children_count: 1,
                sibling_index: 1,
                row_offset: 2,
              },
              2: {
                path: { field_2: 'C' },
                depth: 0,
                row_count: 1,
                children_count: 1,
                sibling_index: 2,
                row_offset: 3,
              },
            },
          },
        },
        absoluteRows: {},
        revision: 0,
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    let groupByRequestParams = null
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByRequestParams = config.params
        return [
          200,
          {
            pages: [
              {
                parent: { field_2: 'A' },
                groups: [
                  {
                    path: { field_2: 'A', field_3: 'Todo' },
                    depth: 1,
                    row_count: 2,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                ],
                offset: 0,
                limit: 1,
                group_count: 1,
              },
              {
                parent: { field_2: 'B' },
                groups: [
                  {
                    path: { field_2: 'B', field_3: 'Done' },
                    depth: 1,
                    row_count: 1,
                    sibling_index: 0,
                    row_offset: 2,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 1,
              },
            ],
          },
        ]
      })

    let rowsRequestParams = null
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      rowsRequestParams = config.params
      return [
        200,
        {
          count: 4,
          results: [
            {
              id: 10,
              order: '1.00',
              field_1: 'Alice',
              field_2: 'A',
              field_3: 'Todo',
            },
            {
              id: 11,
              order: '2.00',
              field_1: 'Ada',
              field_2: 'A',
              field_3: 'Todo',
            },
            {
              id: 12,
              order: '3.00',
              field_1: 'Bea',
              field_2: 'B',
              field_3: 'Done',
            },
            {
              id: 13,
              order: '4.00',
              field_1: 'Cleo',
              field_2: 'C',
              field_3: 'Todo',
            },
          ],
        },
      ]
    })

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      scrollTop: 0,
    })

    // Expanded groups load their children per parent (parents=...), descending to the
    // leaves in one request (include_descendants), never by depth.
    expect(groupByRequestParams.get('depth')).toBe(null)
    expect(groupByRequestParams.get('include_descendants')).toBe('true')
    expect(groupByRequestParams.get('parents')).not.toBe(null)
    expect(rowsRequestParams.get('offset')).toBe('0')
    expect(rowsRequestParams.get('limit')).toBe('4')
    expect(
      store.state.grid.groupBy.pages[groupPathKey(2, 'A')].nodes[0].path
    ).toEqual({
      field_2: 'A',
      field_3: 'Todo',
    })
    expect(
      store.state.grid.groupBy.pages[groupPathKey(2, 'B')].nodes[0].path
    ).toEqual({
      field_2: 'B',
      field_3: 'Done',
    })
  })

  test('group-by data fetch places cached absolute rows into newly loaded visible sections', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
      { id: 3, name: 'Status', type: 'text' },
    ]
    const groupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 2,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 1,
            nodes: {
              0: {
                path: { field_2: 'A' },
                depth: 0,
                row_count: 2,
                children_count: 1,
                sibling_index: 0,
                row_offset: 0,
              },
            },
          },
        },
        absoluteRows: {
          0: {
            id: 10,
            order: '1.00',
            field_1: 'Alice',
            field_2: 'A',
            field_3: 'Todo',
          },
          1: {
            id: 11,
            order: '2.00',
            field_1: 'Ada',
            field_2: 'A',
            field_3: 'Todo',
          },
        },
        revision: 0,
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(200, {
      pages: [
        {
          parent: { field_2: 'A' },
          groups: [
            {
              path: { field_2: 'A', field_3: 'Todo' },
              depth: 1,
              row_count: 2,
              sibling_index: 0,
              row_offset: 0,
            },
          ],
          offset: 0,
          limit: 40,
          group_count: 1,
        },
      ],
    })

    await store.dispatch('grid/fetchGroupByData', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      parentRequests: [{ parentPath: { field_2: 'A' }, offset: 0, limit: 40 }],
      adhocFiltering: false,
    })

    expect(Object.values(store.state.grid.groupBy.sectionRows).flat()).toEqual([
      state.groupBy.absoluteRows[0],
      state.groupBy.absoluteRows[1],
    ])
  })

  test('group-by viewport scroll descends visible groups to leaves in one request', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
      { id: 3, name: 'Status', type: 'text' },
      { id: 4, name: 'Client', type: 'text' },
    ]
    const groupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
      { field: 4, order: 'ASC', type: 'default' },
    ]
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: groupBys,
      count: 2,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 1,
            nodes: {
              0: {
                path: { field_2: 'A' },
                depth: 0,
                row_count: 2,
                children_count: 1,
                sibling_index: 0,
                row_offset: 0,
              },
            },
          },
        },
        absoluteRows: {},
        revision: 0,
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    const groupByRequests = []
    mockServer.mock
      .onGet('/database/views/grid/1/group-by-data/')
      .reply((config) => {
        groupByRequests.push(config.params)
        // include_descendants returns the whole visible subtree (A -> Todo -> Acme)
        // down to the leaves in this single response.
        return [
          200,
          {
            pages: [
              {
                parent: { field_2: 'A' },
                groups: [
                  {
                    path: { field_2: 'A', field_3: 'Todo' },
                    depth: 1,
                    row_count: 2,
                    children_count: 1,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 1,
              },
              {
                parent: { field_2: 'A', field_3: 'Todo' },
                groups: [
                  {
                    path: {
                      field_2: 'A',
                      field_3: 'Todo',
                      field_4: 'Acme',
                    },
                    depth: 2,
                    row_count: 2,
                    sibling_index: 0,
                    row_offset: 0,
                  },
                ],
                offset: 0,
                limit: 40,
                group_count: 1,
              },
            ],
          },
        ]
      })

    const rowRequests = []
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      rowRequests.push(config.params)
      return [
        200,
        {
          count: 2,
          results: [
            {
              id: 10,
              order: '1.00',
              field_1: 'Alice',
              field_2: 'A',
              field_3: 'Todo',
              field_4: 'Acme',
            },
            {
              id: 11,
              order: '2.00',
              field_1: 'Ada',
              field_2: 'A',
              field_3: 'Todo',
              field_4: 'Acme',
            },
          ],
        },
      ]
    })

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields,
      scrollTop: 0,
    })

    // One request descends the visible groups to their leaves (include_descendants),
    // instead of one request per level on scroll.
    expect(groupByRequests).toHaveLength(1)
    expect(groupByRequests[0].get('depth')).toBe(null)
    expect(groupByRequests[0].get('parents')).not.toBe(null)
    expect(groupByRequests[0].get('include_descendants')).toBe('true')
    expect(rowRequests).toHaveLength(1)
    const rowsRequestParams = rowRequests[0]
    expect(rowsRequestParams.get('offset')).toBe('0')
    expect(rowsRequestParams.get('limit')).toBe('2')
    expect(
      Object.values(store.state.grid.groupBy.sectionRows)
        .flat()
        .map((row) => row.id)
    ).toEqual([10, 11])
  })

  test('group-by viewport fetch uses one request and splits rows into sections', async () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      count: 3,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    let requestParams = null
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      requestParams = config.params
      return [
        200,
        {
          count: 3,
          results: [
            { id: 10, order: '1.00', field_1: 'Alice', field_2: 'A' },
            { id: 11, order: '2.00', field_1: 'Bob', field_2: 'A' },
            { id: 12, order: '3.00', field_1: 'Carol', field_2: 'B' },
          ],
        },
      ]
    })

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
      },
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      scrollTop: 0,
    })

    expect(mockServer.mock.history.get).toHaveLength(1)
    expect(requestParams.get('offset')).toBe('0')
    expect(requestParams.get('limit')).toBe('3')
    expect(requestParams.get('group_path')).toBe(null)
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (row) => row.id
      )
    ).toEqual([10, 11])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')].map(
        (row) => row.id
      )
    ).toEqual([12])
  })

  test('group-by row section fetch reuses an in-flight absolute range request', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      count: 2,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 2 }],
        pages: {},
        absoluteRows: {},
        revision: 0,
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    const requestResolvers = []
    let requestCount = 0
    mockServer.mock.onGet('/database/views/grid/1/').reply(() => {
      requestCount += 1
      return new Promise((resolve) => {
        requestResolvers.push(() =>
          resolve([
            200,
            {
              count: 2,
              results: [
                { id: 10, order: '1.00', field_1: 'Alice', field_2: 'A' },
                { id: 11, order: '2.00', field_1: 'Ada', field_2: 'A' },
              ],
            },
          ])
        )
      })
    })

    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
    }
    const layout = store.getters['grid/getGroupByLayout']
    const sections = [
      {
        sectionKey: groupPathKey(2, 'A'),
        sectionPath: { field_2: 'A' },
        absoluteRowOffset: 0,
        rowCount: 2,
        startPosition: 0,
        endPosition: 2,
      },
    ]
    const firstRequest = store.dispatch('grid/fetchGroupByRowsForSections', {
      gridId: 1,
      view,
      fields,
      sections,
      layout,
    })
    await Promise.resolve()

    const secondRequest = store.dispatch('grid/fetchGroupByRowsForSections', {
      gridId: 1,
      view,
      fields,
      sections,
      layout,
    })

    await vi.waitFor(() => expect(requestCount).toBe(1))
    requestResolvers.forEach((resolve) => resolve())
    await Promise.all([firstRequest, secondRequest])

    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (row) => row.id
      )
    ).toEqual([10, 11])
  })

  test('group-by viewport fetch uses absolute offsets for expanded groups', async () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      count: 4,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 2 },
        ],
        truncated: false,
        collapse: { mode: 'collapse', paths: [{ field_2: 'A' }] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    let requestParams = null
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      requestParams = config.params
      return [
        200,
        {
          count: 2,
          results: [
            { id: 10, order: '1.00', field_1: 'Alice', field_2: 'A' },
            { id: 11, order: '2.00', field_1: 'Ada', field_2: 'A' },
            { id: 12, order: '3.00', field_1: 'Bob', field_2: 'B' },
            { id: 13, order: '4.00', field_1: 'Bea', field_2: 'B' },
          ],
        },
      ]
    })

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
      },
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      scrollTop: 0,
    })

    expect(mockServer.mock.history.get).toHaveLength(1)
    expect(requestParams.get('offset')).toBe('0')
    expect(requestParams.get('limit')).toBe('4')
    expect(requestParams.get('group_path')).toBe(null)
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (row) => row.id
      )
    ).toEqual([10, 11])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')]
    ).toBeUndefined()
  })

  test('group-by viewport fetch skips already loaded section rows', async () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      count: 2,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 2 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        { id: 10, order: '1.00', field_1: 'Alice', field_2: 'A' },
        { id: 11, order: '2.00', field_1: 'Bob', field_2: 'A' },
      ],
      startPosition: 0,
    })

    await store.dispatch('grid/fetchGroupByRowsByScrollTop', {
      gridId: 1,
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: [{ field: 2, order: 'ASC', type: 'default' }],
      },
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      scrollTop: 0,
    })

    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('group collapse preserves loaded rows and only fetches missing visible slots', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'Team', type: 'text' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 4,
      rowHeight: 33,
      rowPadding: 0,
      windowHeight: 330,
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 2 },
        ],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        { id: 10, order: '1.00', field_1: 'Alice', field_2: 'A' },
        { id: 11, order: '2.00', field_1: 'Ada', field_2: 'A' },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [
        { id: 12, order: '3.00', field_1: 'Bob', field_2: 'B' },
        { id: 13, order: '4.00', field_1: 'Bea', field_2: 'B' },
      ],
      startPosition: 0,
    })

    const view = {
      id: 1,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
      sortings: [],
      group_bys: groupBys,
    }

    await store.dispatch('grid/toggleGroupCollapse', {
      path: { field_2: 'B' },
      view,
      fields,
      adhocFiltering: false,
    })
    await store.dispatch('grid/toggleGroupCollapse', {
      path: { field_2: 'B' },
      view,
      fields,
      adhocFiltering: false,
    })

    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (row) => row.id
      )
    ).toEqual([10, 11])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')].map(
        (row) => row.id
      )
    ).toEqual([12, 13])
    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('evicts least-recently-used group-by section rows beyond the retained cap', () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 1 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
          { path: { field_2: 'C' }, depth: 0, row_count: 1 },
        ],
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
        sectionAccessOrder: [],
      },
    })
    store.replaceState({ ...store.state, grid: state })

    // Loaded oldest-to-newest: A, then B, then C.
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [{ id: 10, order: '1.00', field_2: 'A' }],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [{ id: 11, order: '2.00', field_2: 'B' }],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'C'),
      rows: [{ id: 12, order: '3.00', field_2: 'C' }],
      startPosition: 0,
    })

    store.commit('grid/EVICT_LRU_GROUP_BY_SECTIONS', { cap: 2 })

    // Oldest (A) evicted; the two most-recent (B, C) retained.
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')]
    ).toBeUndefined()
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')].map(
        (r) => r.id
      )
    ).toEqual([11])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'C')].map(
        (r) => r.id
      )
    ).toEqual([12])
    // The evicted section's rowLocations entry is cleaned; retained ones stay.
    expect(store.state.grid.groupBy.rowLocations[10]).toBeUndefined()
    expect(store.state.grid.groupBy.rowLocations[11]).toBeDefined()
  })

  test('re-touching a group-by section protects it from LRU eviction', () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 1 },
          { path: { field_2: 'B' }, depth: 0, row_count: 1 },
        ],
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
        sectionAccessOrder: [],
      },
    })
    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [{ id: 10, order: '1.00', field_2: 'A' }],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [{ id: 11, order: '2.00', field_2: 'B' }],
      startPosition: 0,
    })
    // Re-touch A so it becomes the most recently used again.
    store.commit('grid/TOUCH_GROUP_BY_SECTIONS', {
      sectionKeys: [groupPathKey(2, 'A')],
    })

    store.commit('grid/EVICT_LRU_GROUP_BY_SECTIONS', { cap: 1 })

    // A was re-touched so it survives; B (now least-recent) is evicted.
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')].map(
        (r) => r.id
      )
    ).toEqual([10])
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'B')]
    ).toBeUndefined()
    expect(store.state.grid.groupBy.rowLocations[11]).toBeUndefined()
  })

  test('stops threading server offsets after an optimistic tree count change', () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 1, order: 'ASC', type: 'default' }],
      groupBy: {
        treeNodes: [{ path: { field_1: 'A' }, depth: 0, row_count: 1 }],
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
        sectionAccessOrder: [],
        offsetsServerConfirmed: true,
      },
    })
    store.replaceState({ ...store.state, grid: state })

    expect(store.state.grid.groupBy.offsetsServerConfirmed).toBe(true)

    store.commit('grid/UPDATE_GROUP_BY_TREE_PATH_COUNT', {
      path: { field_1: 'A' },
      fields: [{ id: 1 }],
      delta: 1,
    })

    // After an optimistic count change the locally-recomputed offsets may diverge
    // from the server, so the row-offset shortcut must be disabled.
    expect(store.state.grid.groupBy.offsetsServerConfirmed).toBe(false)
  })

  test('group-by section fetch preserves selected cell state for known rows', () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 12,
          order: '3.00',
          field_1: 'Carol',
          field_2: 'A',
          _: {
            selected: true,
            selectedFieldId: 1,
            selectedBy: [1],
            loading: false,
          },
        },
      ],
      startPosition: 0,
    })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'A'),
      rows: [
        {
          id: 12,
          order: '3.00',
          field_1: 'Carol',
          field_2: 'A',
          _: {
            selected: false,
            selectedFieldId: -1,
            selectedBy: [],
            loading: false,
          },
        },
      ],
      startPosition: 0,
    })

    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')][0]._.selected
    ).toBe(true)
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')][0]._
        .selectedFieldId
    ).toBe(1)
    expect(
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')][0]._.selectedBy
    ).toEqual([1])
  })

  test('group-by visible items render sparse section row ranges loaded by scroll', () => {
    const state = Object.assign(gridStore.state(), {
      scrollTop: 2 * 48 + 8 + 33 * 25,
      windowHeight: 330,
      rowHeight: 33,
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      groupBy: {
        treeNodes: [
          { path: { field_2: 'A' }, depth: 0, row_count: 2 },
          { path: { field_2: 'B' }, depth: 0, row_count: 100 },
        ],
        truncated: false,
        collapse: { mode: 'collapse', paths: [{ field_2: 'B' }] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: groupPathKey(2, 'B'),
      rows: [{ id: 30, order: '30.00', field_1: 'Deep row', field_2: 'B' }],
      startPosition: 25,
    })

    expect(() =>
      store.getters['grid/getGroupByVisibleItems']([
        { id: 2, name: 'Team', type: 'text' },
      ])
    ).not.toThrow()
    expect(
      store.getters['grid/getGroupByVisibleItems']([
        { id: 2, name: 'Team', type: 'text' },
      ]).some((item) => item.type === 'row' && item.row.id === 30)
    ).toBe(true)
  })

  test('group-by finalize keeps selected row state and removes temporary row location', () => {
    const state = Object.assign(gridStore.state(), {
      activeGroupBys: [{ field: 2, order: 'ASC', type: 'default' }],
      groupBy: {
        treeNodes: [{ path: { field_2: 'A' }, depth: 0, row_count: 1 }],
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })

    const row = {
      id: 'temporary-id',
      order: '3.00',
      field_1: '',
      field_2: 'A',
      _: {
        selected: true,
        selectedFieldId: 1,
        selectedBy: [1],
        loading: true,
      },
    }
    store.commit('grid/INSERT_ROW_AT_LOCATION', {
      sectionKey: groupPathKey(2, 'A'),
      position: 0,
      row,
    })

    store.commit('grid/FINALIZE_ROWS_IN_BUFFER', {
      oldRows: [row],
      newRows: [{ id: 12, order: '4.00', field_1: '', field_2: 'A' }],
      fields: ['field_1', 'field_2'],
    })

    const finalizedRow =
      store.state.grid.groupBy.sectionRows[groupPathKey(2, 'A')][0]
    expect(finalizedRow.id).toBe(12)
    expect(finalizedRow._.loading).toBe(false)
    expect(finalizedRow._.selected).toBe(true)
    expect(finalizedRow._.selectedFieldId).toBe(1)
    expect(
      store.state.grid.groupBy.rowLocations['temporary-id']
    ).toBeUndefined()
    expect(store.state.grid.groupBy.rowLocations[12]).toEqual({
      sectionKey: groupPathKey(2, 'A'),
      position: 0,
    })
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

    store.replaceState({ ...store.state, grid: state })

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

  test('createdNewRow is idempotent for an already-present row', async () => {
    // On reconnect a live ``rows_created`` can be both delivered live and
    // replayed, so ``createdNewRow`` must be a no-op for a row already in the
    // store rather than inserting a duplicate and inflating the count.
    const state = Object.assign(gridStore.state(), {
      bufferStartIndex: 0,
      bufferLimit: 3,
      rows: [
        { id: 1, order: '1.00000000000000000000' },
        { id: 2, order: '2.00000000000000000000' },
        { id: 3, order: '3.00000000000000000000' },
      ],
      count: 3,
    })
    store.replaceState({ ...store.state, grid: state })

    const view = { filters: [], sortings: [], ownership_type: 'collaborative' }

    await store.dispatch('grid/createdNewRow', {
      view,
      fields: [],
      values: { id: 2, order: '2.00000000000000000000' },
      getScrollTop: () => 0,
    })

    expect(store.getters['grid/getAllRows'].length).toBe(3)
    expect(store.getters['grid/getCount']).toBe(3)
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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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
    const store = createStore({
      modules: {
        grid: {
          ...gridStore,
          state: () => state,
        },
      },
    })

    const nuxtApp = useNuxtApp()

    store.$registry = nuxtApp.$registry

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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

    expect(store.getters['grid/getFieldIdByIndex'](2, fields)).toBe(3)
  })

  test('hides a collaborator group whose last row optimistically moves out', async () => {
    const fields = [
      { id: 1, name: 'Name', type: 'text', primary: true },
      { id: 2, name: 'People', type: 'multiple_collaborators' },
    ]
    const groupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const meta = (id) => ({
      selected: false,
      selectedFieldId: -1,
      selectedBy: [],
      loading: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: `r${id}`,
    })
    const aKey = groupPathKey(2, [100])
    const bKey = groupPathKey(2, [200])
    const cKey = groupPathKey(2, [300])
    const r10 = {
      id: 10,
      order: '1.00',
      field_1: 'A row',
      field_2: [{ id: 100 }],
      _: meta(10),
    }
    const r11 = {
      id: 11,
      order: '2.00',
      field_1: 'B row',
      field_2: [{ id: 200 }],
      _: meta(11),
    }

    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: groupBys,
      count: 2,
      rowHeight: 33,
      windowHeight: 2000,
      fieldOptions: {
        1: { hidden: false, order: 0 },
        2: { hidden: false, order: 1 },
      },
      groupBy: {
        treeNodes: [
          {
            path: { field_2: [100] },
            depth: 0,
            row_count: 1,
            sibling_index: 0,
            row_offset: 0,
          },
          {
            path: { field_2: [200] },
            depth: 0,
            row_count: 1,
            sibling_index: 1,
            row_offset: 1,
          },
        ],
        pages: {
          '': {
            parentPath: {},
            totalSiblingCount: 2,
            nodes: {
              0: {
                path: { field_2: [100] },
                depth: 0,
                row_count: 1,
                sibling_index: 0,
                row_offset: 0,
              },
              1: {
                path: { field_2: [200] },
                depth: 0,
                row_count: 1,
                sibling_index: 1,
                row_offset: 1,
              },
            },
          },
        },
        absoluteRows: {},
        truncated: false,
        collapse: { mode: 'expand', paths: [] },
        sectionRows: {},
        rowLocations: {},
      },
    })
    store.replaceState({ ...store.state, grid: state })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: aKey,
      rows: [r10],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: bKey,
      rows: [r11],
      startPosition: 0,
    })

    const moved = store.getters['grid/getRow'](10)
    moved.field_2 = [{ id: 300 }]
    moved._.matchSortings = false
    await store.dispatch('grid/refreshRow', {
      grid: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: moved,
      fields,
    })

    const items = store.getters['grid/getGroupByVisibleItems']([fields[1]])
    const headerKeys = items
      .filter((item) => item.type === 'header')
      .map((item) => pathKey(item.path, [fields[1]]))

    // The emptied group (100) is hidden; the new (300) and untouched (200) remain.
    expect(headerKeys).not.toContain(aKey)
    expect(headerKeys).toContain(bKey)
    expect(headerKeys).toContain(cKey)

    // The source node is kept at row_count 0 for reconciliation, just not rendered.
    const sourceNode = store.state.grid.groupBy.treeNodes.find(
      (node) => pathKey(node.path, [fields[1]]) === aKey
    )
    expect(sourceNode.row_count).toBe(0)
  })
})
