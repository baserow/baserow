import gridStore from '@baserow/modules/database/store/view/grid'
import { TestApp } from '@baserow/test/helpers/testApp'
import {
  EqualViewFilterType,
  ContainsViewFilterType,
} from '@baserow/modules/database/viewFilters'
import { clone } from '@baserow/modules/core/utils/object'

import { createStore } from 'vuex'

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
      sectionKey: '"A"',
      rows: [
        { id: 10, order: '1.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 11, order: '2.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: '"B"',
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
      sectionKey: '"A"',
      rows: [
        { id: 10, order: '1.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 11, order: '2.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: '"B"',
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
      sectionKey: '"A"',
      rows: [
        { id: 10, order: '1.00', _: { selected: false, selectedFieldId: -1 } },
        { id: 11, order: '2.00', _: { selected: false, selectedFieldId: -1 } },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: '"B"',
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
      sectionKey: '"A"',
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
      sectionKey: '"A"',
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
      sectionKey: '"A"',
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
      sectionKey: '"B"',
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

  test('updateRowValue warns then moves selected single-select rows between group-by sections on unselect', async () => {
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
      sectionKey: `${optionA.id}`,
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
      sectionKey: `${optionB.id}`,
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

    const movedRow = store.getters['grid/getRow'](10)
    expect(store.state.grid.groupBy.sectionRows[`${optionA.id}`]).toHaveLength(
      1
    )
    expect(movedRow.field_2).toEqual(optionB)
    expect(movedRow._.matchSortings).toBe(false)
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: optionA.id }, depth: 0, row_count: 1 },
      { path: { field_2: optionB.id }, depth: 0, row_count: 1 },
    ])
    expect(mockServer.mock.history.get).toHaveLength(0)

    await store.dispatch('grid/removeRowSelectedBy', {
      grid: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      row: movedRow,
      field: fields[1],
      fields,
    })

    expect(store.state.grid.groupBy.sectionRows[`${optionA.id}`]).toEqual([])
    expect(
      store.state.grid.groupBy.sectionRows[`${optionB.id}`].map((row) => row.id)
    ).toEqual([10, 11])
    expect(movedRow._.matchSortings).toBe(true)
    expect(store.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: optionA.id }, depth: 0, row_count: 0 },
      { path: { field_2: optionB.id }, depth: 0, row_count: 2 },
    ])
    expect(mockServer.mock.history.get).toHaveLength(0)
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
      sectionKey: '"B"',
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
      store.state.grid.groupBy.sectionRows['"B"'].map((row) => [
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
      sectionKey: '"B"',
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

    const optimisticRow = groupByStore.state.grid.groupBy.sectionRows['"B"'][1]
    expect(optimisticRow).toBeDefined()
    expect(optimisticRow._.matchSortings).toBe(true)

    finishCreate()
    await createPromise
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
      sectionKey: '"A"',
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

    const optimisticRow = groupByStore.state.grid.groupBy.sectionRows['"A"'][1]
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
      groupByStore.state.grid.groupBy.sectionRows['"A"'].map((row) => row.id)
    ).toEqual([10])
    expect(groupByStore.state.grid.groupBy.treeNodes).toEqual([
      { path: { field_2: 'A' }, depth: 0, row_count: 1 },
    ])
    expect(groupByStore.getters['grid/getCount']).toBe(1)
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
      sectionKey: '"A"',
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
      sectionKey: '"B"',
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
      pasteStore.state.grid.groupBy.sectionRows['"B"'].map((row) => [
        row.id,
        row.field_1,
      ])
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
      sectionKey: '"A"',
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
      sectionKey: '"B"',
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
      sectionKey: '"A"',
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

  test('refresh enables group-by mode before choosing the refresh path', async () => {
    const fetchGroupByTree = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByTree,
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
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: [],
      rowHeight: 33,
      windowHeight: 330,
    })

    groupByStore.replaceState({ ...groupByStore.state, grid: state })

    await groupByStore.dispatch('grid/refresh', {
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
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.activeGroupBys).toEqual([
      { field: 2, order: 'ASC', type: 'default' },
    ])
    expect(groupByStore.state.grid.groupBy.collapse).toEqual({
      mode: 'collapse',
      paths: [],
    })
    expect(fetchGroupByTree).toHaveBeenCalledOnce()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
    expect(correctMultiSelect).toHaveBeenCalledOnce()
    expect(fetchAllFieldAggregationData).toHaveBeenCalledOnce()
  })

  test('refresh preserves group-by collapse state when already grouped', async () => {
    const fetchGroupByTree = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByTree,
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
    expect(fetchGroupByTree).toHaveBeenCalledOnce()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
  })

  test('refresh preserves group-by collapse state when adding a group-by', async () => {
    const fetchGroupByTree = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByTree,
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
    const initialGroupBys = [{ field: 2, order: 'ASC', type: 'default' }]
    const nextGroupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const collapse = {
      mode: 'collapse',
      paths: [{ field_2: 'A' }],
    }
    const state = Object.assign(gridStore.state(), {
      lastGridId: 1,
      activeGroupBys: initialGroupBys,
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
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: nextGroupBys,
      },
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
        { id: 3, name: 'Role', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.activeGroupBys).toEqual(nextGroupBys)
    expect(groupByStore.state.grid.groupBy.collapse).toEqual(collapse)
    expect(fetchGroupByTree).toHaveBeenCalledOnce()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
  })

  test('refresh preserves group-by collapse state when removing a group-by', async () => {
    const fetchGroupByTree = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByTree,
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
    const initialGroupBys = [
      { field: 2, order: 'ASC', type: 'default' },
      { field: 3, order: 'ASC', type: 'default' },
    ]
    const nextGroupBys = [{ field: 2, order: 'ASC', type: 'default' }]
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

    await groupByStore.dispatch('grid/refresh', {
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: nextGroupBys,
      },
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
    expect(fetchGroupByTree).toHaveBeenCalledOnce()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
  })

  test('refresh preserves initialized group-by collapse state when re-enabling group-by', async () => {
    const fetchGroupByTree = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const correctMultiSelect = vi.fn()
    const fetchAllFieldAggregationData = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByTree,
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

    await groupByStore.dispatch('grid/refresh', {
      view: {
        id: 1,
        filters: [],
        filter_groups: [],
        filter_type: 'AND',
        sortings: [],
        group_bys: groupBys,
      },
      fields: [
        { id: 1, name: 'Name', type: 'text', primary: true },
        { id: 2, name: 'Team', type: 'text' },
      ],
      adhocFiltering: false,
      adhocSorting: false,
    })

    expect(groupByStore.state.grid.activeGroupBys).toEqual(groupBys)
    expect(groupByStore.state.grid.groupBy.collapse).toEqual(collapse)
    expect(fetchGroupByTree).toHaveBeenCalledOnce()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
  })

  test('fetchInitial uses group-by mode after syncing active group-bys', async () => {
    const fetchGroupByTree = vi.fn()
    const fetchGroupByRowsByScrollTop = vi.fn()
    const updateSearch = vi.fn()
    const groupByActions = {
      ...gridStore.actions,
      fetchGroupByTree,
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
      mode: 'collapse',
      paths: [],
    })
    expect(fetchGroupByTree).toHaveBeenCalledOnce()
    expect(fetchGroupByRowsByScrollTop).toHaveBeenCalledOnce()
    expect(updateSearch).toHaveBeenCalledOnce()
    expect(mockServer.mock.history.get).toHaveLength(0)
  })

  test('fetchInitial keeps field options when group-by loads collapsed', async () => {
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

    mockServer.mock.onGet('/database/views/grid/1/group-tree/').reply(200, {
      nodes: [
        { path: { field_2: 'A' }, depth: 0, row_count: 2 },
        { path: { field_2: 'B' }, depth: 0, row_count: 1 },
      ],
      truncated: false,
      total_nodes: 2,
    })

    let requestParams = null
    mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
      requestParams = config.params
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

    expect(requestParams.get('include')).toBe('field_options')
    expect(requestParams.get('limit')).toBe('0')
    expect(requestParams.get('group_visibility_paths')).toBe(null)
    expect(requestParams.get('group_visibility_mode')).toBe(null)
    expect(groupByStore.state.grid.fieldOptions).toEqual({
      1: { hidden: false, order: 0 },
      2: { hidden: false, order: 1 },
    })
    expect(groupByStore.state.grid.groupBy.sectionRows).toEqual({})
  })

  test('group-by tree fetch sets global grouped row count', async () => {
    mockServer.mock.onGet('/database/views/grid/1/group-tree/').reply(200, {
      nodes: [
        { path: { field_2: 'A' }, depth: 0, row_count: 2 },
        { path: { field_2: 'B' }, depth: 0, row_count: 3 },
      ],
      truncated: false,
      total_nodes: 2,
    })

    await store.dispatch('grid/fetchGroupByTree', {
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

    expect(store.state.grid.count).toBe(5)
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
    expect(requestParams.get('group_visibility_paths')).toBe(null)
    expect(requestParams.get('group_visibility_mode')).toBe(null)
    expect(requestParams.get('group_path')).toBe(null)
    expect(
      store.state.grid.groupBy.sectionRows['"A"'].map((row) => row.id)
    ).toEqual([10, 11])
    expect(
      store.state.grid.groupBy.sectionRows['"B"'].map((row) => row.id)
    ).toEqual([12])
  })

  test('group-by viewport fetch sends collapse visibility for expanded groups', async () => {
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
    expect(requestParams.get('limit')).toBe('2')
    expect(JSON.parse(requestParams.get('group_visibility_paths'))).toEqual([
      { field_2: 'A' },
    ])
    expect(requestParams.get('group_visibility_mode')).toBe('collapse')
    expect(requestParams.get('group_path')).toBe(null)
    expect(
      store.state.grid.groupBy.sectionRows['"A"'].map((row) => row.id)
    ).toEqual([10, 11])
    expect(store.state.grid.groupBy.sectionRows['"B"']).toBeUndefined()
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
      sectionKey: '"A"',
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
      sectionKey: '"A"',
      rows: [
        { id: 10, order: '1.00', field_1: 'Alice', field_2: 'A' },
        { id: 11, order: '2.00', field_1: 'Ada', field_2: 'A' },
      ],
      startPosition: 0,
    })
    store.commit('grid/SET_GROUP_BY_SECTION_ROWS', {
      sectionKey: '"B"',
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
      store.state.grid.groupBy.sectionRows['"A"'].map((row) => row.id)
    ).toEqual([10, 11])
    expect(
      store.state.grid.groupBy.sectionRows['"B"'].map((row) => row.id)
    ).toEqual([12, 13])
    expect(mockServer.mock.history.get).toHaveLength(0)
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
      sectionKey: '"A"',
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
      sectionKey: '"A"',
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

    expect(store.state.grid.groupBy.sectionRows['"A"'][0]._.selected).toBe(true)
    expect(
      store.state.grid.groupBy.sectionRows['"A"'][0]._.selectedFieldId
    ).toBe(1)
    expect(store.state.grid.groupBy.sectionRows['"A"'][0]._.selectedBy).toEqual(
      [1]
    )
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
      sectionKey: '"B"',
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
      sectionKey: '"A"',
      position: 0,
      row,
    })

    store.commit('grid/FINALIZE_ROWS_IN_BUFFER', {
      oldRows: [row],
      newRows: [{ id: 12, order: '4.00', field_1: '', field_2: 'A' }],
      fields: ['field_1', 'field_2'],
    })

    const finalizedRow = store.state.grid.groupBy.sectionRows['"A"'][0]
    expect(finalizedRow.id).toBe(12)
    expect(finalizedRow._.loading).toBe(false)
    expect(finalizedRow._.selected).toBe(true)
    expect(finalizedRow._.selectedFieldId).toBe(1)
    expect(
      store.state.grid.groupBy.rowLocations['temporary-id']
    ).toBeUndefined()
    expect(store.state.grid.groupBy.rowLocations[12]).toEqual({
      sectionKey: '"A"',
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

  test('UPDATE_GROUP_BY_METADATA mutation', () => {
    const state = Object.assign(gridStore.state(), {})

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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

  test('group by metadata ignores created and deleted rows outside view filters', async () => {
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
            field_1: 'a',
            count: 2,
          },
        ],
      },
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
          field: 2,
          type: EqualViewFilterType.getType(),
          value: 'visible',
        },
      ],
      sortings: [],
      ownership_type: 'collaborative',
    }
    const fields = [
      {
        id: 1,
        name: 'Group',
        type: 'text',
        primary: true,
      },
      {
        id: 2,
        name: 'Visibility',
        type: 'text',
        primary: false,
      },
    ]
    const hiddenRow = {
      id: 1,
      order: '1.00000000000000000000',
      field_1: 'a',
      field_2: 'hidden',
    }
    const getScrollTop = () => 0

    await store.dispatch('grid/createdNewRow', {
      view,
      fields,
      values: hiddenRow,
      getScrollTop,
    })
    expect(store.state.grid.groupByMetadata.field_1[0].count).toBe(2)

    await store.dispatch('grid/deletedExistingRow', {
      view,
      fields,
      row: hiddenRow,
      getScrollTop,
    })
    expect(store.state.grid.groupByMetadata.field_1[0].count).toBe(2)
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

    store.replaceState({ ...store.state, grid: state })

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

    store.replaceState({ ...store.state, grid: state })

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
