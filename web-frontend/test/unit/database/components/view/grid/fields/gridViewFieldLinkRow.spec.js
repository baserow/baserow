import { h } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import GridViewFieldLinkRow from '@baserow/modules/database/components/view/grid/fields/GridViewFieldLinkRow'
import SelectRowModal from '@baserow/modules/database/components/row/SelectRowModal'

const ids = (value) => value.map(({ id }) => id)

describe('GridViewFieldLinkRow component', () => {
  let testApp = null

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
      users: [],
    })
    await testApp.store.dispatch('application/forceCreate', {
      id: 1,
      type: 'database',
      workspace: { id: 1 },
      tables: [
        { id: 10, name: 'Orders', database_id: 1 },
        { id: 11, name: 'Payments', database_id: 1 },
        { id: 12, name: 'Other', database_id: 1 },
      ],
    })
    const database = testApp.store.getters['application/get'](1)
    const table = database.tables[0]
    testApp.store.commit('table/SET_SELECTED', { database, table })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  // The cell shows a row modal's row, and each `update` stands for the PATCH.
  async function mountCell({ tableId }) {
    const { store } = testApp
    await store.dispatch('rowModal/open', {
      componentId: 'modal',
      tableId,
      id: 7,
      exists: true,
      row: { id: 7, order: '1.00', field_1: [] },
    })
    const field = {
      id: 1,
      table_id: tableId,
      type: 'link_row',
      link_row_table_id: 11,
      link_row_related_field_id: 21,
      link_row_multiple_relationships: true,
    }
    const getRow = () => store.getters['rowModal/get']('modal').row
    const patched = []
    const wrapper = await testApp.mount(
      {
        render: () =>
          h(GridViewFieldLinkRow, {
            field,
            value: getRow().field_1,
            row: getRow(),
            selected: true,
            storePrefix: 'page/',
            workspaceId: 1,
            onUpdate: (value) => {
              patched.push(ids(value))
              store.dispatch('rowModal/updated', {
                tableId,
                values: { id: 7, field_1: value },
              })
            },
          }),
      },
      {}
    )
    const select = async (row, created = false) => {
      wrapper.findComponent(SelectRowModal).vm.$emit('selected', {
        row: { order: '1.00', field_20: `Payment ${row.id}`, ...row },
        primary: { id: 20, type: 'text' },
        created,
      })
      await flushPromises()
    }
    return { patched, select, shown: () => ids(getRow().field_1) }
  }

  test('a row created with the link back shows without a PATCH and stays on the next pick', async () => {
    const { patched, select, shown } = await mountCell({ tableId: 10 })

    await select({ id: 99, field_21: [{ id: 7 }] }, true)
    expect(shown()).toEqual([99])
    expect(patched).toEqual([])

    await select({ id: 50, field_21: [] })
    expect(patched).toEqual([[50, 99]])
  })

  test.each([
    ['a created row without the link back', 10, [], true],
    [
      'a listed row, whose link back can predate an unlink',
      10,
      [{ id: 7 }],
      false,
    ],
    ['a created row of another table', 12, [{ id: 7 }], true],
  ])('%s is PATCHed', async (_, tableId, linkBack, created) => {
    const { patched, select } = await mountCell({ tableId })

    await select({ id: 99, field_21: linkBack }, created)

    expect(patched).toEqual([[99]])
  })
})
