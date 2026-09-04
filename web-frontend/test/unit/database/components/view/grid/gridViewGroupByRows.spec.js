import GridViewGroupByRows from '@baserow/modules/database/components/view/grid/GridViewGroupByRows'
import { pathKey } from '@baserow/modules/database/utils/gridGroupByRender'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('GridViewGroupByRows component', () => {
  let testApp = null
  let store = null

  const fields = [
    { id: 1, name: 'Team', type: 'text', primary: true, text_default: '' },
  ]
  const groupBys = [
    { id: 10, field: 1, order: 'ASC', type: 'default', width: 200 },
  ]
  const makeRow = (id, team) => ({
    id,
    field_1: team,
    _: {
      loading: false,
      selected: false,
      hover: false,
      matchFilters: true,
      matchSortings: true,
      matchSearch: true,
      fieldSearchMatches: [],
      persistentId: id,
    },
  })

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('continues column group boundaries across row cells only in Columns', async () => {
    const rowsA = [makeRow(1, 'A'), makeRow(2, 'A')]
    const rowsB = [makeRow(3, 'B')]
    store.commit('page/view/grid/APPLY_GROUP_BY_STATE', {
      activeGroupBys: groupBys,
      count: 3,
      groupBy: {
        treeNodes: [
          { path: { field_1: 'A' }, depth: 0, row_count: 2 },
          { path: { field_1: 'B' }, depth: 0, row_count: 1 },
        ],
        pages: {},
        absoluteRows: {},
        revision: 0,
        generation: 0,
        aggregationsLoading: false,
        aggregationsLoadingPaths: [],
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
        sectionRows: {
          [pathKey({ field_1: 'A' }, fields)]: rowsA,
          [pathKey({ field_1: 'B' }, fields)]: rowsB,
        },
        rowLocations: {},
        sectionAccessOrder: [],
        addRowHoverPathKey: null,
        offsetsServerConfirmed: true,
      },
    })
    store.commit('page/view/grid/SET_WINDOW_HEIGHT', 1000)
    await store.dispatch('page/view/grid/setGroupByLayout', 'column')

    const wrapper = await testApp.mount(GridViewGroupByRows, {
      props: {
        renderedFields: fields,
        visibleFields: fields,
        allVisibleFields: fields,
        allFieldsInTable: fields,
        decorationsByPlace: {},
        groupColumnsWidth: 200,
        view: {
          id: 1,
          table: {},
          sortings: [],
          row_identifier_type: 'count',
        },
        includeRowDetails: true,
        readOnly: false,
        workspaceId: 1,
        storePrefix: 'page/',
      },
      global: {
        stubs: { GridViewRow: true, GridViewGroupByBanner: true },
      },
    })

    expect(wrapper.findAll('.grid-view__group-by-rows-row')).toHaveLength(3)
    expect(
      wrapper.findAll('.grid-view__group-by-rows-row--group-end')
    ).toHaveLength(2)

    await store.dispatch('page/view/grid/setGroupByLayout', 'banner')
    await wrapper.vm.$nextTick()

    expect(
      wrapper.findAll('.grid-view__group-by-rows-row--group-end')
    ).toHaveLength(0)
  })
})
