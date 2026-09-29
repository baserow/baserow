import { h } from 'vue'
import flushPromises from 'flush-promises'
import PublicViewExportMenuItem from '@baserow_premium/components/views/PublicViewExportMenuItem.vue'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'

const gridCases = ['saved', 'clear', 'replace'].flatMap((groupMode) =>
  ['clear', 'replace'].map((sortMode) => ({ groupMode, sortMode }))
)
const expectedGroup = { saved: 'field_1', clear: '', replace: '-field_3' }
const expectedSort = { clear: '', replace: '-field_4' }

describe('Public view export preserves effective grouping', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const prepareView = async (type = 'grid') => {
    const { view } = await store.dispatch('view/forceCreate', {
      data: {
        id: 1,
        type,
        slug: 'shared-view',
        allow_public_export: true,
        table: { id: 1, database_id: 1 },
        ownership_type: 'collaborative',
        filter_type: 'AND',
        filters: [],
        filter_groups: [],
        group_bys:
          type === 'grid'
            ? [{ id: 10, view: 1, field: 1, order: 'ASC', type: 'default' }]
            : [],
        sortings: [
          { id: 20, view: 1, field: 2, order: 'ASC', type: 'default' },
        ],
      },
    })
    await store.dispatch('page/view/public/setIsPublic', true)
    return view
  }

  const exportView = async (view) => {
    const client = testApp.getApp().$client
    const url = `/database/view/${view.slug}/export-public-view/`
    testApp.mock.onPost(url).reply(200, { id: 1 })
    const wrapper = await testApp.mount(PublicViewExportMenuItem, {
      props: {
        database: { id: 1 },
        table: { id: 1 },
        fields: [],
        storePrefix: 'page/',
        view,
      },
      global: {
        stubs: {
          // Only the generic modal UI is replaced. The mounted menu item's
          // callback, view registry, serializers, service and Axios are real.
          ExportTableModal: {
            props: ['startExport', 'view'],
            render() {
              return h(
                'button',
                {
                  type: 'button',
                  onClick: () =>
                    this.startExport({
                      view: this.view,
                      values: { exporter_type: 'csv', view_id: this.view.id },
                      client,
                    }),
                },
                'Export CSV'
              )
            },
          },
        },
      },
    })
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(testApp.mock.history.post).toHaveLength(1)
    const request = testApp.mock.history.post[0]
    expect(request.url).toBe(url)
    const values = JSON.parse(request.data)
    expect(values.exporter_type).toBe('csv')
    expect(values).not.toHaveProperty('view_id')
    return values
  }

  test.each(gridCases)(
    'grid export after grouping=$groupMode and sorting=$sortMode',
    async ({ groupMode, sortMode }) => {
      const view = await prepareView()
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
      } else {
        await store.dispatch('view/updateSort', {
          sort: view.sortings[0],
          values: { field: 4, order: 'DESC' },
          readOnly: true,
        })
      }

      expect(testApp.mock.history.delete).toHaveLength(0)
      expect(testApp.mock.history.patch).toHaveLength(0)
      const values = await exportView(view)
      expect(values.order_by).toBe(expectedSort[sortMode])
      // An absent key means inherit saved groups. Empty means the visitor
      // removed all groups; those are different requests even for exports.
      expect(values).toHaveProperty('group_by', expectedGroup[groupMode])
    }
  )

  test.each(['gallery', 'kanban', 'calendar'])(
    '%s export omits group_by because the view cannot group rows',
    async (type) => {
      const view = await prepareView(type)
      const values = await exportView(view)
      expect(values.order_by).toBe('field_2')
      expect(values).not.toHaveProperty('group_by')
    }
  )
})
