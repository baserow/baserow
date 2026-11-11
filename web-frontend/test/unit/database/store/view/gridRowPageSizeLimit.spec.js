import gridStore from '@baserow/modules/database/store/view/grid'
import GridService from '@baserow/modules/database/services/view/grid'
import { TestApp } from '@baserow/test/helpers/testApp'

const view = {
  id: 1,
  type: 'grid',
  filter_type: 'AND',
  filters: [],
  filter_groups: [],
  filters_disabled: false,
  sortings: [],
  group_bys: [{ id: 1, view: 1, field: 1, order: 'ASC', type: 'default' }],
}

// Replies to the grid rows endpoint with one row per requested position, using the
// position as the row id, and records the requested ranges.
const mockGridRows = (mockServer, requests) => {
  mockServer.mock.onGet('/database/views/grid/1/').reply((config) => {
    const offset = Number(config.params.get('offset') || 0)
    const limit = Number(config.params.get('limit'))
    requests.push({
      offset,
      limit,
      include: config.params.get('include'),
      excludeCount: config.params.has('exclude_count'),
    })
    const results = []
    const rowMetadata = {}
    for (let id = offset; id < offset + limit; id++) {
      results.push({ id, order: `${id}.00`, field_1: 'A' })
      rowMetadata[id] = { position: id }
    }
    return [
      200,
      {
        count: 1000,
        results,
        row_metadata: rowMetadata,
        ...(offset === 0 ? { field_options: { 1: { hidden: false } } } : {}),
      },
    ]
  })
}

describe('Grid view rows respect the row page size limit', () => {
  let testApp = null
  let mockServer = null
  let store = null
  let originalLimit = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
    store = testApp.createStore({ modules: { grid: gridStore } })
    originalLimit = store.$config.public.baserowRowPageSizeLimit
    store.$config.public.baserowRowPageSizeLimit = 200
  })

  afterEach(async () => {
    store.$config.public.baserowRowPageSizeLimit = originalLimit
    await testApp.afterEach()
  })

  test('fetchRowsInChunks splits a large limit and merges the responses', async () => {
    const requests = []
    mockGridRows(mockServer, requests)

    const { data } = await GridService(store.$client).fetchRowsInChunks({
      chunkSize: 200,
      gridId: 1,
      offset: 0,
      limit: 450,
      includeFieldOptions: true,
    })

    expect(requests.map(({ offset, limit }) => ({ offset, limit }))).toEqual([
      { offset: 0, limit: 200 },
      { offset: 200, limit: 200 },
      { offset: 400, limit: 50 },
    ])
    // Field options are only needed once.
    expect(requests.map(({ include }) => include)).toEqual([
      'field_options,row_metadata',
      'row_metadata',
      'row_metadata',
    ])
    // The count is only needed once.
    expect(requests.map(({ excludeCount }) => excludeCount)).toEqual([
      false,
      true,
      true,
    ])
    expect(data.results.map((row) => row.id)).toEqual(
      Array.from({ length: 450 }, (_, index) => index)
    )
    expect(Object.keys(data.row_metadata)).toHaveLength(450)
    expect(data.count).toBe(1000)
    expect(data.field_options).toEqual({ 1: { hidden: false } })
  })

  test('fetchRowsInChunks makes a single request within the limit', async () => {
    const requests = []
    mockGridRows(mockServer, requests)

    const { data } = await GridService(store.$client).fetchRowsInChunks({
      chunkSize: 200,
      gridId: 1,
      offset: 10,
      limit: 200,
    })

    expect(requests).toHaveLength(1)
    expect(requests[0]).toMatchObject({ offset: 10, limit: 200 })
    expect(data.results).toHaveLength(200)
  })

  test('rows hidden between sections are not fetched', async () => {
    const requests = []
    mockGridRows(mockServer, requests)
    store.replaceState({
      ...store.state,
      grid: Object.assign(gridStore.state(), {
        activeGroupBys: [{ field: 1 }],
        count: 1000000,
      }),
    })

    // Two visible groups with a large collapsed group in between, so the
    // visible rows are almost a million positions apart in the absolute row space.
    const sections = [
      { absoluteRowOffset: 0, startPosition: 0, endPosition: 10 },
      { absoluteRowOffset: 999900, startPosition: 0, endPosition: 10 },
    ]
    const data = await store.dispatch('grid/fetchGroupByRowsForSections', {
      gridId: 1,
      view,
      fields: [{ id: 1, type: 'text', name: 'Text' }],
      sections,
      layout: { items: [] },
    })

    // Each section is padded to whole buffer pages of 40 rows.
    expect(requests.map(({ offset, limit }) => ({ offset, limit }))).toEqual([
      { offset: 0, limit: 80 },
      { offset: 999840, limit: 120 },
    ])
    // Only the first window asks for the count.
    expect(requests.map(({ excludeCount }) => excludeCount)).toEqual([
      false,
      true,
    ])
    const ids = data.results.map((row) => row.id)
    expect(ids).toContain(9)
    expect(ids).toContain(999909)
  })

  test('refreshing does not fetch the rows of a collapsed group between visible groups', async () => {
    const requests = []
    mockGridRows(mockServer, requests)
    store.replaceState({
      ...store.state,
      grid: Object.assign(gridStore.state(), {
        lastGridId: 1,
        activeGroupBys: view.group_bys,
        count: 1000000,
        rowHeight: 33,
        rowPadding: 0,
        windowHeight: 3300,
        fieldOptions: { 1: { hidden: false, order: 0 } },
        groupBy: {
          ...gridStore.state().groupBy,
          collapse: { mode: 'expand', paths: [{ field_1: 'B' }] },
          collapseInitialized: true,
        },
      }),
    })
    const groups = [
      { value: 'A', rowCount: 5, rowOffset: 0 },
      { value: 'B', rowCount: 999990, rowOffset: 5 },
      { value: 'C', rowCount: 5, rowOffset: 999995 },
    ]
    mockServer.mock.onGet('/database/views/grid/1/group-by-data/').reply(200, {
      pages: [
        {
          parent: {},
          groups: groups.map(({ value, rowCount, rowOffset }, index) => ({
            path: { field_1: value },
            depth: 0,
            row_count: rowCount,
            sibling_index: index,
            row_offset: rowOffset,
          })),
          offset: 0,
          limit: 40,
          group_count: 3,
        },
      ],
    })

    await store.dispatch('grid/refreshActiveGroupBys', {
      view,
      fields: [{ id: 1, type: 'text', name: 'Text' }],
      scrollTop: 0,
      preserveScroll: true,
    })

    // One window per visible group instead of a range over the collapsed one.
    expect(requests.map(({ offset, limit }) => ({ offset, limit }))).toEqual([
      { offset: 0, limit: 5 },
      { offset: 999995, limit: 5 },
    ])
  })
})
