import GridService from '@baserow/modules/database/services/view/grid'
import { getGroupBy, getOrderBy } from '@baserow/modules/database/utils/view'
import { TestApp } from '@baserow/test/helpers/testApp'

const modes = ['inherit', 'clear', 'replace']
const requestCases = modes.flatMap((groupMode) =>
  modes.map((sortMode) => ({ publicView: false, groupMode, sortMode }))
)
// Public views always send the visitor's effective configuration.
requestCases.push(
  ...modes
    .slice(1)
    .flatMap((groupMode) =>
      modes
        .slice(1)
        .map((sortMode) => ({ publicView: true, groupMode, sortMode }))
    )
)

const expectedGroup = { inherit: null, clear: '', replace: '-field_3' }
const expectedSort = { inherit: null, clear: '', replace: '-field_4' }

// Parse the serialized query string, rather than inspecting helper return values.
const expectOverride = (params, key, expected) => {
  expect({ [key]: params.getAll(key) }).toEqual({
    [key]: expected === null ? [] : [expected],
  })
}

describe('Grid sorting and grouping request contract', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const prepareView = async ({
    publicView,
    groupMode,
    sortMode = 'inherit',
  }) => {
    const { view } = await store.dispatch('view/forceCreate', {
      data: {
        id: 1,
        type: 'grid',
        table: { id: 1, database_id: 1 },
        ownership_type: 'collaborative',
        group_bys: [
          { id: 10, view: 1, field: 1, order: 'ASC', type: 'default' },
        ],
        sortings: [
          { id: 20, view: 1, field: 2, order: 'ASC', type: 'default' },
        ],
      },
    })
    await store.dispatch('page/view/public/setIsPublic', publicView)

    // These are the same local mutations used by an Editor or public visitor;
    // removing the final item must not silently restore the saved server config.
    if (groupMode === 'clear') {
      await store.dispatch('view/deleteGroupBy', {
        view,
        groupBy: view.group_bys[0],
        readOnly: true,
      })
      expect(view.group_bys).toEqual([])
    } else if (groupMode === 'replace') {
      await store.dispatch('view/updateGroupBy', {
        groupBy: view.group_bys[0],
        values: { field: 3, order: 'DESC' },
        readOnly: true,
      })
    }

    if (sortMode === 'clear') {
      await store.dispatch('view/deleteSort', {
        view,
        sort: view.sortings[0],
        readOnly: true,
      })
      expect(view.sortings).toEqual([])
    } else if (sortMode === 'replace') {
      await store.dispatch('view/updateSort', {
        sort: view.sortings[0],
        values: { field: 4, order: 'DESC' },
        readOnly: true,
      })
    }

    expect(testApp.mock.history.delete).toHaveLength(0)
    expect(testApp.mock.history.patch).toHaveLength(0)
    return view
  }

  test.each(requestCases)(
    'rows: public=$publicView, grouping=$groupMode, sorting=$sortMode',
    async ({ publicView, groupMode, sortMode }) => {
      const view = await prepareView({ publicView, groupMode, sortMode })
      const gridId = publicView ? 'shared-grid' : view.id
      const url = `/database/views/grid/${gridId}/${publicView ? 'public/rows/' : ''}`
      testApp.mock.onGet(url).reply(200, { results: [], count: 0 })

      await GridService(testApp.getApp().$client).fetchRows({
        gridId,
        publicUrl: publicView,
        groupBy: getGroupBy(
          store.getters,
          view.id,
          !publicView && groupMode !== 'inherit'
        ),
        orderBy: getOrderBy(view, sortMode !== 'inherit'),
      })

      expect(testApp.mock.history.get).toHaveLength(1)
      const request = testApp.mock.history.get[0]
      expect(request.url).toBe(url)
      const params = new URLSearchParams(request.params.toString())
      expectOverride(params, 'order_by', expectedSort[sortMode])
      expectOverride(params, 'group_by', expectedGroup[groupMode])
    }
  )

  test.each([
    { publicView: false, groupMode: 'inherit' },
    { publicView: false, groupMode: 'clear' },
    { publicView: false, groupMode: 'replace' },
    { publicView: true, groupMode: 'clear' },
    { publicView: true, groupMode: 'replace' },
  ])(
    'group metadata: public=$publicView, grouping=$groupMode',
    async ({ publicView, groupMode }) => {
      const view = await prepareView({ publicView, groupMode })
      const gridId = publicView ? 'shared-grid' : view.id
      const url = `/database/views/grid/${gridId}/${publicView ? 'public/' : ''}group-by-data/`
      testApp.mock.onGet(url).reply(200, { results: [] })

      await GridService(testApp.getApp().$client).fetchGroupByData({
        gridId,
        publicUrl: publicView,
        groupBy: getGroupBy(
          store.getters,
          view.id,
          !publicView && groupMode !== 'inherit'
        ),
      })

      expect(testApp.mock.history.get).toHaveLength(1)
      const params = new URLSearchParams(
        testApp.mock.history.get[0].params.toString()
      )
      expectOverride(params, 'group_by', expectedGroup[groupMode])
    }
  )

  test.each([
    { method: 'fetchRows', publicView: false },
    { method: 'fetchRows', publicView: true },
    { method: 'fetchGroupByData', publicView: false },
    { method: 'fetchGroupByData', publicView: true },
  ])(
    '$method without overrides inherits server settings (public=$publicView)',
    async ({ method, publicView }) => {
      testApp.mock.onGet().reply(200, { results: [] })
      await GridService(testApp.getApp().$client)[method]({
        gridId: publicView ? 'shared-grid' : 1,
        publicUrl: publicView,
      })
      expect(testApp.mock.history.get).toHaveLength(1)
      const params = new URLSearchParams(
        testApp.mock.history.get[0].params.toString()
      )
      expectOverride(params, 'group_by', null)
      expectOverride(params, 'order_by', null)
    }
  )
})
