import { TestApp, UIHelpers } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

import Table from '@baserow/modules/database/pages/table'
import { test } from 'vitest'

describe('Table Component Tests', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(async () => await testApp.afterEach())

  test('Adding a row to a table increases the row count', async () => {
    const { application, table, gridView } =
      await givenASingleSimpleTableInTheServer()

    const tableComponent = await testApp.mount(Table, {
      route: `/database/${application.id}/table/${table.id}/${gridView.id}?token=fake`,
    })

    expect(tableComponent.html()).toMatchSnapshot()

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

    await flushPromises()

    expect(tableComponent.html()).toMatchSnapshot()
  })

  test('Searching for a cells value highlights it', async () => {
    const { application, table, gridView } =
      await givenASingleSimpleTableInTheServer()

    mockServer.mock.onGet(`/database/field-rules/${table.id}/`).reply(200, [])

    const tableComponent = await testApp.mount(Table, {
      route: `/database/${application.id}/table/${table.id}/${gridView.id}?token=fake`,
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

    await flushPromises()

    expect(
      tableComponent
        .findAll('.grid-view__column--matches-search')
        .filter((w) => w.html().includes('last_name')).length
    ).toBe(1)
  })

  test.skip('Editing a search highlighted cells value so it will no longer match warns', async () => {
    const { application, table, gridView } =
      await givenASingleSimpleTableInTheServer()

    const tableComponent = await testApp.mount(Table, {
      route: `/database/${application.id}/table/${table.id}/${gridView.id}?token=fake`,
    })

    await flushPromises()

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
    await flushPromises()
    expect(
      tableComponent.html().includes('gridViewRow.rowNotMatchingSearch')
    ).toBe(true)

    await input.setValue('last_name')
    await flushPromises()

    expect(tableComponent.html()).not.toContain(
      'gridViewRow.rowNotMatchingSearch'
    )
  })

  async function givenASingleSimpleTableInTheServer() {
    mockServer.fakeSettings()
    mockServer.fakeAuthentication()

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
