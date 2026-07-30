import { TestApp, UIHelpers } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

import Table from '@baserow/modules/database/pages/table'
import { RefreshCancelledError } from '@baserow/modules/core/errors'
import { test, vi } from 'vitest'

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

  test('Second refresh fires after first completes instead of being swallowed', async () => {
    const { gridView, tableComponent } = await givenAMountedTable()

    const { resolveFirstCount, getRequestCount } =
      setupGridRefreshMocks(gridView)

    const innerTable = tableComponent.findComponent({ name: 'Table' })

    const firstRefresh = innerTable.vm.refresh({})
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(getRequestCount()).toBe(1)

    const secondRefresh = innerTable.vm.refresh({})

    resolveFirstCount()
    await firstRefresh
    await secondRefresh
    await flushPromises()

    expect(getRequestCount()).toBeGreaterThan(2)
  })

  test('Three rapid refreshes: all run sequentially via queue', async () => {
    const { gridView, tableComponent } = await givenAMountedTable()

    const { resolveFirstCount, getRequestCount } =
      setupGridRefreshMocks(gridView)

    const innerTable = tableComponent.findComponent({ name: 'Table' })

    const callbackOrder = []
    const firstRefresh = innerTable.vm.refresh({
      callback: () => {
        callbackOrder.push('first')
      },
    })
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(getRequestCount()).toBe(1)

    innerTable.vm.refresh({
      callback: () => {
        callbackOrder.push('second')
      },
    })
    const thirdRefresh = innerTable.vm.refresh({
      callback: () => {
        callbackOrder.push('third')
      },
    })

    resolveFirstCount()
    await firstRefresh
    await thirdRefresh
    await flushPromises()

    // 5 not 6: first task's fetchRows is aborted (signal already cancelled
    // by onSuperseded when tasks 2/3 were added), so only fetchCount fires.
    expect(getRequestCount()).toBe(5)
    expect(callbackOrder).toEqual(['first', 'second', 'third'])
  })

  test('Refresh queue drains after concurrent refreshes complete', async () => {
    const { gridView, tableComponent } = await givenAMountedTable()

    const { resolveFirstCount } = setupGridRefreshMocks(gridView)

    const innerTable = tableComponent.findComponent({ name: 'Table' })

    const firstRefresh = innerTable.vm.refresh({})
    await new Promise((resolve) => setTimeout(resolve, 0))

    const secondRefresh = innerTable.vm.refresh({})

    resolveFirstCount()
    await firstRefresh
    await secondRefresh
    await flushPromises()

    expect(innerTable.vm.refreshQueue.queue.length).toBe(0)
    expect(innerTable.vm.refreshQueue.running).toBe(false)
  })

  test('Callback still runs when refresh is cancelled by abort', async () => {
    const { gridView, tableComponent } = await givenAMountedTable()

    setupGridRefreshMocks(gridView)

    const innerTable = tableComponent.findComponent({ name: 'Table' })
    const viewType = testApp._app.$registry.get('view', 'grid')
    const originalRefresh = viewType.refresh.bind(viewType)

    let callCount = 0
    vi.spyOn(viewType, 'refresh').mockImplementation((...args) => {
      callCount++
      if (callCount === 1) {
        throw new RefreshCancelledError()
      }
      return originalRefresh(...args)
    })

    let callbackRan = false
    const refresh = innerTable.vm.refresh({
      callback: () => {
        callbackRan = true
      },
    })

    await refresh
    await flushPromises()

    expect(callbackRan).toBe(true)

    viewType.refresh.mockRestore()
  })

  async function givenAMountedTable() {
    const { application, table, gridView } =
      await givenASingleSimpleTableInTheServer()
    const tableComponent = await testApp.mount(Table, {
      route: `/database/${application.id}/table/${table.id}/${gridView.id}?token=fake`,
    })
    return { application, table, gridView, tableComponent }
  }

  function setupGridRefreshMocks(gridView) {
    mockServer.resetMockEndpoints()
    let resolveFirstCount
    let gridRequestCount = 0
    const row = {
      id: 1,
      order: '1.00',
      field_1: 'name',
      field_2: 'last_name',
      field_3: 'notes',
      field_4: false,
    }
    mockServer.mock.onGet(`/database/views/grid/${gridView.id}/`).reply(() => {
      gridRequestCount++
      if (gridRequestCount === 1) {
        return new Promise((resolve) => {
          resolveFirstCount = () => resolve([200, { count: 1 }])
        })
      }
      return [200, { count: 1, results: [row] }]
    })
    mockServer.mock
      .onGet(`/database/views/grid/${gridView.id}/aggregations/`)
      .reply(200, {})
    return {
      resolveFirstCount: () => resolveFirstCount(),
      getRequestCount: () => gridRequestCount,
    }
  }

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
