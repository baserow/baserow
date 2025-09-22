import { TestApp, UIHelpers } from '@baserow/test/helpers/testApp'
import Table from '@baserow/modules/database/pages/table'
import flushPromises from 'flush-promises'

// Mock out debounce so we dont have to wait or simulate waiting for the various
// debounces in the search functionality.
jest.mock('lodash/debounce', () => jest.fn((fn) => fn))

describe('Table Component Tests', () => {
  let testApp = null
  let mockServer = null

  beforeAll(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(() => testApp.afterEach())

  test('Adding a row to a table increases the row count', async () => {
    const { application, table, gridView } =
      await givenASingleSimpleTableInTheServer()

    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: gridView.id,
      },
    })

    expect(tableComponent.html()).toContain('gridView.rowCount - 1')

    mockServer.creatingRowsInTableReturns(table, {
      items: [
        {
          id: 2,
          order: '2.00000000000000000000',
          field_1: '',
          field_2: '',
          field_3: '',
          field_4: false,
        },
      ],
    })

    const button = tableComponent.find('.grid-view__add-row')
    await button.trigger('click')

    // Wait a moment until the row is added. This is needed because the store
    // actions have an await.
    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(tableComponent.html()).toContain('gridView.rowCount - 2')
  })

  test('Searching for a cells value highlights it', async () => {
    const { application, table, gridView } =
      await givenASingleSimpleTableInTheServer()

    mockServer.mock.onGet(`/database/field-rules/${table.id}/`).reply(200, [])

    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: gridView.id,
      },
    })

    mockServer.resetMockEndpoints()
    mockServer.nextSearchForTermWillReturn('last_name', gridView, [
      {
        id: 1,
        order: 0,
        field_1: 'name',
        field_2: 'last_name',
        field_3: 'notes',
        field_4: false,
      },
    ])

    await UIHelpers.performSearch(tableComponent, 'last_name')

    expect(
      tableComponent
        .findAll('.grid-view__column--matches-search')
        .filter((w) => w.html().includes('last_name')).length
    ).toBe(1)
  })

  test('Editing a search highlighted cells value so it will no longer match warns', async () => {
    const { application, table, gridView } =
      await givenASingleSimpleTableInTheServer()

    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: gridView.id,
      },
    })

    mockServer.resetMockEndpoints()
    mockServer.nextSearchForTermWillReturn('last_name', gridView, [
      {
        id: 1,
        order: 0,
        field_1: 'name',
        field_2: 'last_name',
        field_3: 'notes',
        field_4: false,
      },
    ])

    await UIHelpers.performSearch(tableComponent, 'last_name')

    const input = await UIHelpers.startEditForCellContaining(
      tableComponent,
      'last_name'
    )

    await input.setValue('Doesnt Match Search Term')
    expect(tableComponent.html()).toContain('gridViewRow.rowNotMatchingSearch')

    await input.setValue('last_name')
    expect(tableComponent.html()).not.toContain(
      'gridViewRow.rowNotMatchingSearch'
    )
    await flushPromises()
  })

  async function givenASingleSimpleTableInTheServer() {
    const table = mockServer.createTable()
    mockServer.mock.onGet(`/database/field-rules/${table.id}/`).reply(200, [])

    const { application } = await mockServer.createAppAndWorkspace(table)
    const gridView = mockServer.createGridView(application, table, {})
    const fields = mockServer.createFields(application, table, [
      {
        name: 'Name',
        type: 'text',
        primary: true,
        read_only: false,
      },
      {
        name: 'Last name',
        type: 'text',
        read_only: false,
      },
      {
        name: 'Notes',
        type: 'long_text',
        read_only: false,
      },
      {
        name: 'Active',
        type: 'boolean',
        read_only: false,
      },
    ])

    mockServer.createGridRows(gridView, fields, [
      {
        id: 1,
        order: 0,
        field_1: 'name',
        field_2: 'last_name',
        field_3: 'notes',
        field_4: false,
      },
    ])
    return { application, table, gridView }
  }
})
