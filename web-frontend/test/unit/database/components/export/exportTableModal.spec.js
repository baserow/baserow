import { TestApp } from '@baserow/test/helpers/testApp'
import ExportTableModal from '@baserow/modules/database/components/export/ExportTableModal'

// Assign a static uuid for the Checkbox clip path ID.
jest.mock('@baserow/modules/core/utils/string', () => ({
  uuid: () => '8bc60af5-c9d8-4370-a4cf-55634b98360d',
}))

describe('Preview exportTableModal', () => {
  let testApp = null
  let mockServer = null

  beforeAll(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => {
    testApp.afterEach()
  })

  async function givenThereIsATableWithView() {
    let table = mockServer.createTable()
    const database = { tables: [], workspace: { id: 0 } }
    table = await testApp.store.dispatch('table/forceUpsert', {
      database,
      data: table,
    })
    const view = mockServer.createGridView(database, table, {})
    return { database, table, view }
  }

  test('Modal with no view', async () => {
    const { table, database } = await givenThereIsATableWithView()
    const wrapper = await testApp.mount(ExportTableModal, {
      propsData: {
        database,
        table,
        view: null,
      },
    })
    await wrapper.vm.show()
    expect(wrapper.element).toMatchSnapshot()
    expect(wrapper.html()).toContain(`exportTableModal.title`)
    expect(wrapper.find('.select__item.active').html()).toContain(
      'exportEntireTable'
    )
  })

  test('Modal with view', async () => {
    const { table, view, database } = await givenThereIsATableWithView()
    const wrapper = await testApp.mount(ExportTableModal, {
      propsData: {
        database,
        table,
        view,
      },
    })
    await wrapper.vm.show()
    expect(wrapper.element).toMatchSnapshot()
    expect(wrapper.find('.select__item.active').html()).toContain(
      `${view.name}`
    )
  })
})
