import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewGroupByColumns from '@baserow/modules/database/components/view/grid/GridViewGroupByColumns'

describe('GridViewGroupByColumns component', () => {
  let testApp = null
  let store = null

  const fields = [
    { id: 1, name: 'Team', type: 'text', primary: true },
    { id: 2, name: 'Role', type: 'text', primary: false },
  ]
  const groupBys = [
    { id: 10, field: 1, order: 'ASC', type: 'default', width: 120 },
    { id: 11, field: 2, order: 'ASC', type: 'default', width: 90 },
  ]

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const seedGroups = async (treeNodes) => {
    store.commit('page/view/grid/APPLY_GROUP_BY_STATE', {
      activeGroupBys: groupBys,
      groupBy: {
        treeNodes,
        pages: {},
        absoluteRows: {},
        revision: 0,
        generation: 0,
        aggregationsLoading: false,
        aggregationsLoadingPaths: [],
        collapse: { mode: 'expand', paths: [] },
        collapseInitialized: true,
        sectionRows: {},
        rowLocations: {},
        sectionAccessOrder: [],
        addRowHoverPathKey: null,
        offsetsServerConfirmed: true,
      },
    })
    await store.dispatch('page/view/grid/setGroupByLayout', 'column')
  }

  const mountColumns = (props = {}) =>
    testApp.mount(GridViewGroupByColumns, {
      props: {
        allFieldsInTable: fields,
        workspaceId: 1,
        storePrefix: 'page/',
        ...props,
      },
    })

  test('renders one cell per visible span, positioned per level, with value and count', async () => {
    await seedGroups([
      { path: { field_1: 'A' }, depth: 0, row_count: 3 },
      { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 2 },
      { path: { field_1: 'A', field_2: 'Y' }, depth: 1, row_count: 1 },
    ])
    const wrapper = await mountColumns()

    const spans = wrapper.findAll('.grid-view__group-span')
    expect(spans).toHaveLength(3)
    expect(spans[0].attributes('style')).toContain('left: 0px')
    expect(spans[0].attributes('style')).toContain('width: 120px')
    expect(spans[0].attributes('style')).toContain('height: 99px')
    expect(spans[1].attributes('style')).toContain('left: 120px')
    expect(spans[1].attributes('style')).toContain('width: 90px')
    expect(spans[2].attributes('style')).toContain('top: 66px')
    expect(spans[0].find('.grid-view__group-value').text()).toBe('A')
    expect(spans[0].find('.grid-view__group-count').text()).toBe('3')
    expect(spans[1].find('.grid-view__group-value').text()).toBe('X')
    expect(spans[2].find('.grid-view__group-count').text()).toBe('1')
    expect(
      wrapper.find('.grid-view__group-columns').attributes('style')
    ).toContain('width: 210px')
  })

  test('renders the empty label for a group without a value', async () => {
    await seedGroups([
      { path: { field_1: '' }, depth: 0, row_count: 1 },
      { path: { field_1: '', field_2: '' }, depth: 1, row_count: 1 },
    ])
    const wrapper = await mountColumns()

    const empties = wrapper.findAll('.grid-view__group-value-empty')
    expect(empties).toHaveLength(2)
    expect(empties[0].text()).toBe('gridViewGroupByBanner.emptyValue')
  })

  test('uses responsive widths without changing the configured group widths', async () => {
    await seedGroups([
      { path: { field_1: 'A' }, depth: 0, row_count: 1 },
      { path: { field_1: 'A', field_2: 'X' }, depth: 1, row_count: 1 },
    ])
    const wrapper = await mountColumns({ groupByWidths: [80, 100] })

    const spans = wrapper.findAll('.grid-view__group-span')
    expect(spans[0].attributes('style')).toContain('width: 80px')
    expect(spans[1].attributes('style')).toContain('left: 80px')
    expect(spans[1].attributes('style')).toContain('width: 100px')
    expect(
      wrapper.find('.grid-view__group-columns').attributes('style')
    ).toContain('width: 180px')
    expect(groupBys.map(({ width }) => width)).toEqual([120, 90])
  })
})
