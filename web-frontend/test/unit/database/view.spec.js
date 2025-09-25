import { TestApp } from '@baserow/test/helpers/testApp'
import Table from '@baserow/modules/database/pages/table'
import {
  DEFAULT_VIEW_ID_COOKIE_NAME,
  readDefaultViewIdFromCookie,
  decodeDefaultViewIdPerTable,
  encodeDefaultViewIdPerTable,
} from '@baserow/modules/database/utils/view'

// Mock out debounce so we don't have to wait or simulate waiting for the various
// debounces in the search functionality.
jest.mock('lodash/debounce', () => jest.fn((fn) => fn))

describe('View Tests', () => {
  let testApp = null
  let mockServer = null
  let originalReplaceFunc = null

  beforeAll(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer

    // Mock the redirect function so we can test the component without having to
    // worry about the router.
    originalReplaceFunc = testApp._app.$router.replace
    testApp._app.$router.replace = ({ params }) => {
      return Table.asyncData({
        app: testApp._app,
        store: testApp._app.store,
        params,
      })
    }
  })

  afterEach(() => testApp.afterEach())

  afterAll(() => {
    testApp._app.$router.replace = originalReplaceFunc
  })

  test('Default view is being set correctly initially', async () => {
    const allCookies = testApp.store.$cookies
    const { application, table, views } =
      await givenATableInTheServerWithMultipleViews()

    const gridView = views[0]
    const galleryView = views[1]
    // The first view is the Grid view, the Default view is the Gallery view which
    // is going to be rendered initially:
    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: galleryView.id,
      },
    })

    const tableId = gridView.table_id

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    // Check if cookie is updated correctly (default view):
    const defaultViewId = readDefaultViewIdFromCookie(allCookies, tableId)
    expect(defaultViewId).not.toBe(null)
    const defaultView = testApp.store.getters['view/get'](defaultViewId)
    expect(defaultView.table_id).toBe(tableId)
    expect(defaultView.id).toBe(galleryView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(galleryView.id)
    // Check if component is rendered:
    expect(tableComponent.find('div.gallery-view').exists()).toBe(true)
    expect(tableComponent.find('div.grid-view').exists()).toBe(false)
  })

  test('Default view is being set correctly after changing views', async () => {
    const { application, table, views } =
      await givenATableInTheServerWithMultipleViews()

    const gridView = views[0]
    const galleryView = views[1]

    // The first view is the Grid view, the Default view is the Gallery view which
    // is going to be rendered initially:
    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: galleryView.id,
      },
    })

    const allCookies = testApp.store.$cookies
    const tableId = gridView.table_id

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    // Check if cookie is updated correctly (default view):
    const defaultViewId = readDefaultViewIdFromCookie(allCookies, tableId)
    expect(defaultViewId).not.toBe(null)
    const defaultView = testApp.store.getters['view/get'](defaultViewId)
    expect(defaultView.table_id).toBe(tableId)
    expect(defaultView.id).toBe(galleryView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(galleryView.id)
    // Check if component is rendered:
    expect(tableComponent.find('div.gallery-view').exists()).toBe(true)
    expect(tableComponent.find('div.grid-view').exists()).toBe(false)

    // Let's switch back (select) the Grid (first) view:
    testApp.store.dispatch('view/selectById', gridView.id)

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    // Check if cookie is updated correctly (default view):
    const updatedCookieValue = decodeDefaultViewIdPerTable(
      allCookies.get(DEFAULT_VIEW_ID_COOKIE_NAME)
    )
    expect(updatedCookieValue.length).toBe(1)
    const updatedDefaultViewId = readDefaultViewIdFromCookie(
      allCookies,
      tableId
    )
    const updatedDefaultView =
      testApp.store.getters['view/get'](updatedDefaultViewId)
    expect(updatedDefaultView.table_id).toBe(tableId)
    expect(updatedDefaultView.id).toBe(gridView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(gridView.id)
  })

  test('Default view is being set correctly after switching tables', async () => {
    const { application, tables, views } =
      await givenATableInTheServerWithMultipleTables()

    const firstTable = tables[0]
    const secondTable = tables[1]
    const firstTableGridView = views[0]
    const secondTableGridView = views[1]

    // The first (and default) view is the Grid view, which is going to be rendered
    // initially for the firstTable:
    const firstTableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: firstTable.id,
      },
    })

    const allCookies = testApp.store.$cookies

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(firstTableGridView.id)
    // Check if cookie is updated correctly (default view):
    const cookieValue = decodeDefaultViewIdPerTable(
      allCookies.get(DEFAULT_VIEW_ID_COOKIE_NAME)
    )
    expect(cookieValue.length).toBe(1)
    const defaultViewId = readDefaultViewIdFromCookie(
      allCookies,
      firstTableGridView.table_id
    )
    expect(defaultViewId).not.toBe(null)
    const defaultView = testApp.store.getters['view/get'](defaultViewId)
    expect(defaultView.table_id).toBe(firstTableGridView.table_id)
    expect(defaultView.id).toBe(firstTableGridView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(firstTableGridView.id)
    // Check if component is rendered:
    expect(firstTableComponent.find('div.grid-view').exists()).toBe(true)
    expect(firstTableComponent.find('div.gallery-view').exists()).toBe(false)

    // The first (and default) view is the Grid view, which is going to be rendered
    // initially for the secondTable:
    await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: secondTable.id,
      },
    })

    // Let's switch to a different table in the database:
    testApp.store.dispatch('table/selectById', {
      databaseId: application.id,
      tableId: secondTable.id,
    })
    testApp.store.dispatch('view/selectById', secondTableGridView.id)

    const allCookiesAfterChangingTable = testApp.store.$cookies
    const cookieValueAfterChangingTable = decodeDefaultViewIdPerTable(
      allCookiesAfterChangingTable.get(DEFAULT_VIEW_ID_COOKIE_NAME)
    )

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(secondTableGridView.id)
    // Check if cookie is updated correctly (default view):
    expect(cookieValueAfterChangingTable.length).toBe(2)
    const defaultViewIdAfterChangingTable = readDefaultViewIdFromCookie(
      allCookies,
      secondTableGridView.table_id
    )
    expect(defaultViewIdAfterChangingTable).not.toBe(null)
    const defaultViewAfterChangingTable = testApp.store.getters['view/get'](
      defaultViewIdAfterChangingTable
    )
    expect(defaultViewAfterChangingTable.table_id).toBe(
      secondTableGridView.table_id
    )
    expect(defaultViewAfterChangingTable.id).toBe(secondTableGridView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(secondTableGridView.id)
    // Check if component is rendered:
    expect(firstTableComponent.find('div.grid-view').exists()).toBe(true)
    expect(firstTableComponent.find('div.gallery-view').exists()).toBe(false)

    // Let's switch back to the first table in the database and see if first table's
    // default view is appended to the *end* of remembered views array:
    await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: firstTable.id,
      },
    })
    testApp.store.dispatch('table/selectById', {
      databaseId: application.id,
      tableId: firstTable.id,
    })
    testApp.store.dispatch('view/selectById', firstTableGridView.id)

    const allCookiesAfterSwitchingBack = testApp.store.$cookies

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(firstTableGridView.id)
    // Check if cookie is updated correctly (default view):
    const cookieValueAfterSwitchingBack = decodeDefaultViewIdPerTable(
      allCookiesAfterSwitchingBack.get(DEFAULT_VIEW_ID_COOKIE_NAME)
    )
    expect(cookieValueAfterSwitchingBack.length).toBe(2)
    const defaultViewIdAfterSwitchingBack = readDefaultViewIdFromCookie(
      allCookiesAfterSwitchingBack,
      firstTableGridView.table_id
    )
    expect(defaultViewIdAfterSwitchingBack).not.toBe(null)
    const defaultViewAfterSwitchingBack = testApp.store.getters['view/get'](
      defaultViewIdAfterSwitchingBack
    )
    expect(defaultViewAfterSwitchingBack.table_id).toBe(
      firstTableGridView.table_id
    )
    expect(defaultViewAfterSwitchingBack.id).toBe(firstTableGridView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(firstTableGridView.id)
  })

  test('Default view is being set correctly only from cookie', async () => {
    // set the cookie, render table without view id passed in, this should render
    // the default (Gallery) view
    const { application, table, views } =
      await givenATableInTheServerWithMultipleViews()

    const gridView = views[0]
    const galleryView = views[1]

    const tableId = gridView.table_id
    const allCookies = testApp.store.$cookies

    // Set the cookie for defaultView manually:
    const defaultViewIdData = []
    defaultViewIdData.push({
      tableId: galleryView.table_id,
      viewId: galleryView.id,
    })
    allCookies.set(
      DEFAULT_VIEW_ID_COOKIE_NAME,
      encodeDefaultViewIdPerTable(defaultViewIdData)
    )

    // The first view is the Grid view, the Default view is the Gallery view,
    // we're not rendering any view initially and Default view (Gallery view)
    // should be picked up from the cookie
    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
      },
    })

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    // Check if cookie is updated correctly (default view):
    const cookieValue = decodeDefaultViewIdPerTable(
      allCookies.get(DEFAULT_VIEW_ID_COOKIE_NAME)
    )
    expect(cookieValue.length).toBe(1)
    const defaultViewId = readDefaultViewIdFromCookie(allCookies, tableId)
    expect(defaultViewId).not.toBe(null)
    const defaultView = testApp.store.getters['view/get'](defaultViewId)
    expect(defaultView.table_id).toBe(tableId)
    expect(defaultView.id).toBe(galleryView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(galleryView.id)
    // Check if component is rendered:
    expect(tableComponent.find('div.gallery-view').exists()).toBe(true)
    expect(tableComponent.find('div.grid-view').exists()).toBe(false)
  })

  test('Changing default view updates cookies array correctly', async () => {
    const { application, table, views } =
      await givenATableInTheServerWithMultipleViews()

    const gridView = views[0]

    // Generate random data to fill up the cookie
    // Our cookie has a limit of 2kb, so we need to generate enough data to fill it up
    // For sure one entry will need more than 1 byte, so we can't just generate 2048
    // entries
    const targetSize = 2048
    const randomData = []
    for (let i = 0; i < targetSize; i++) {
      const randomTableId = i
      const randomViewId = i
      const entry = { tableId: randomTableId, viewId: randomViewId }
      randomData.push(entry)
    }

    const allCookies = testApp.store.$cookies
    allCookies.set(
      DEFAULT_VIEW_ID_COOKIE_NAME,
      encodeDefaultViewIdPerTable(randomData)
    )
    const originalDataLength = randomData.length

    // Mount the component, which should update the cookies
    await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: gridView.id,
      },
    })

    // The Default view is the Grid view and it should be set (appended) in the cookie
    const cookieValue = decodeDefaultViewIdPerTable(
      allCookies.get(DEFAULT_VIEW_ID_COOKIE_NAME)
    )
    expect(cookieValue.length).toBeGreaterThan(0)

    const defaultViewIdObject = cookieValue[cookieValue.length - 1]
    expect(defaultViewIdObject.tableId).toBe(gridView.table_id)
    expect(defaultViewIdObject.viewId).toBe(gridView.id)

    // Check if gridView is set as the last view in the array
    expect(cookieValue[cookieValue.length - 1]).toMatchObject(
      defaultViewIdObject
    )

    // Ensure that the first element is removed from the cookie array
    const updatedCookieValue = decodeDefaultViewIdPerTable(
      allCookies.get(DEFAULT_VIEW_ID_COOKIE_NAME)
    )
    expect(updatedCookieValue).not.toContainEqual(randomData[0])
    expect(updatedCookieValue.length).toBeLessThan(originalDataLength)
  })

  test('Unknown error during views loading is displayed correctly - no view toolbar', async () => {
    const viewsError = { statusCode: 500, data: 'some backend error' }

    // no list of views
    const { application, table } = await givenATableWithError({
      viewsError,
    })
    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: '123',
      },
    })

    expect(tableComponent.vm.views).toEqual([])

    expect(tableComponent.vm.error).toBeTruthy()

    // no table header (view selection, filters, sorting, grouping...)
    expect(tableComponent.find('header .header__filter-link').exists()).toBe(
      false
    )

    expect(tableComponent.find('.placeholder__title').exists()).toBe(true)
    // error message will be processed and replaced
    expect(tableComponent.find('.placeholder__title').text()).toBe(
      'errorLayout.wrong'
    )
    expect(tableComponent.find('.placeholder__content').exists()).toBe(true)

    expect(tableComponent.find('.placeholder__content').text()).toBe(
      'errorLayout.error'
    )
  })

  test('API error during views loading is displayed correctly', async () => {
    const viewsError = {
      statusCode: 400,
      data: {
        message: "The view filter type INVALID doesn't exist.",
      },
    }

    // no list of views
    const { application, table } = await givenATableWithError({
      viewsError,
    })
    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: '123',
      },
    })

    expect(tableComponent.vm.views).toEqual([])
    expect(tableComponent.vm.error).toBeTruthy()

    expect(tableComponent.find('header .header__filter-link').exists()).toBe(
      false
    )
    expect(tableComponent.find('.placeholder__title').exists()).toBe(true)
    expect(tableComponent.find('.placeholder__title').text()).toEqual(
      viewsError.data.message
    )
    expect(tableComponent.find('.placeholder__content').exists()).toBe(true)

    expect(tableComponent.find('.placeholder__content').text()).toEqual(
      'errorLayout.error'
    )
  })

  test('API error during view rows loading', async () => {
    const rowsError = { statusCode: 500, data: { message: 'Unknown error' } }

    // views list readable, fields readable, rows not readable
    const { application, table, view } = await givenATableWithError({
      rowsError,
    })

    //
    const tableComponent = await testApp.mount(Table, {
      asyncDataParams: {
        databaseId: application.id,
        tableId: table.id,
        viewId: view.id,
      },
    })

    expect(tableComponent.vm.views).toMatchObject([view])

    // we're past views api call, so the table (with the error) and toolbar should be present
    expect(tableComponent.find('.header__filter-link').exists()).toBe(true)

    expect(tableComponent.vm.error).toBeTruthy()

    expect(tableComponent.find('.placeholder__title').exists()).toBe(true)
    expect(tableComponent.find('.placeholder__title').text()).toEqual(
      rowsError.data.message
    )
    expect(tableComponent.find('.placeholder__content').exists()).toBe(true)

    expect(tableComponent.find('.placeholder__content').text()).toEqual(
      'errorLayout.error'
    )
  })

  async function givenATableInTheServerWithMultipleViews() {
    const table = mockServer.createTable()
    const { application } = await mockServer.createAppAndWorkspace(table)
    const gridView = mockServer.createGridView(application, table, {
      viewId: 1,
    })
    const galleryView = mockServer.createGalleryView(application, table, {
      viewId: 2,
    })

    mockServer.mock
      .onGet(`/database/views/table/${table.id}/`)
      .reply(200, [gridView, galleryView])
    mockServer.mock.onGet(`/database/field-rules/${table.id}/`).reply(200, [])

    const fields = mockServer.createFields(application, table, [
      {
        name: 'Name',
        type: 'text',
        primary: true,
      },
      {
        name: 'Last name',
        type: 'text',
      },
      {
        name: 'Notes',
        type: 'long_text',
      },
      {
        name: 'Active',
        type: 'boolean',
      },
    ])

    const rows = [
      {
        id: 1,
        order: 0,
        field_1: 'name',
        field_2: 'last_name',
        field_3: 'notes',
        field_4: false,
      },
    ]

    mockServer.createGridRows(gridView, fields, rows)
    mockServer.createFields(application, table, fields)
    mockServer.createGalleryRows(galleryView, fields, rows)

    const views = []
    views.push(gridView)
    views.push(galleryView)
    return { application, table, views }
  }

  async function givenATableInTheServerWithMultipleTables() {
    const firstTable = mockServer.createTable(1, 'Test Table 1')
    const secondTable = mockServer.createTable(2, 'Test Table 2')
    const { application } =
      await mockServer.createAppAndWorkspaceWithMultipleTables([
        firstTable,
        secondTable,
      ])

    // First table - 1 view:
    const firstTableGridView = mockServer.createGridView(
      application,
      firstTable,
      {
        viewId: 1,
      }
    )
    mockServer.mock
      .onGet(`/database/field-rules/${firstTable.id}/`)
      .reply(200, [])
    mockServer.mock
      .onGet(`/database/field-rules/${secondTable.id}/`)
      .reply(200, [])

    mockServer.mock
      .onGet(`/database/views/table/${firstTable.id}/`)
      .reply(200, [firstTableGridView])

    // Second table - 1 view:
    const secondTableGridView = mockServer.createGridView(
      application,
      secondTable,
      {
        viewId: 2,
      }
    )
    mockServer.mock
      .onGet(`/database/views/table/${secondTable.id}/`)
      .reply(200, [secondTableGridView])

    const fields = mockServer.createFields(application, firstTable, [
      {
        name: 'Name',
        type: 'text',
        primary: true,
      },
      {
        name: 'Last name',
        type: 'text',
      },
      {
        name: 'Notes',
        type: 'long_text',
      },
      {
        name: 'Active',
        type: 'boolean',
      },
    ])

    const rows = [
      {
        id: 1,
        order: 0,
        field_1: 'name',
        field_2: 'last_name',
        field_3: 'notes',
        field_4: false,
      },
    ]

    mockServer.createGridRows(firstTableGridView, fields, rows)
    mockServer.createGridRows(secondTableGridView, fields, rows)
    mockServer.createFields(application, firstTable, fields)
    mockServer.createFields(application, secondTable, fields)

    const views = []
    views.push(firstTableGridView)
    views.push(secondTableGridView)

    const tables = []
    tables.push(firstTable)
    tables.push(secondTable)
    return { application, tables, views }
  }

  async function givenATableWithError({ viewsError, fieldsError, rowsError }) {
    const table = mockServer.createTable()
    // we expect some endpoints to return errors
    testApp.dontFailOnErrorResponses()
    const { application } =
      await mockServer.createAppAndWorkspaceWithMultipleTables([table])
    const viewId = 1

    const rawGridView = {
      id: viewId,
      table_id: table.id,
      name: `mock_view_${viewId}`,
      order: 0,
      type: 'grid',
      table: {
        id: table.id,
        name: table.name,
        order: 0,
        database_id: application.id,
      },
      filter_type: 'AND',
      filters_disabled: false,
      public: null,
      row_identifier_type: 'id',
      row_height_size: 'small',
      filters: [],
      sortings: [],
      group_bys: [],
      decorations: [],
      ownership_type: 'collaborative',
    }

    const rawFields = [
      {
        name: 'Name',
        type: 'text',
        primary: true,
      },
      {
        name: 'Last name',
        type: 'text',
      },
      {
        name: 'Notes',
        type: 'long_text',
      },
      {
        name: 'Active',
        type: 'boolean',
      },
    ]
    const rawRows = [
      {
        id: 1,
        order: 0,
        field_1: 'name',
        field_2: 'last_name',
        field_3: 'notes',
        field_4: false,
      },
    ]

    mockServer.mock
      .onGet(`/database/views/table/${table.id}/`)
      .replyOnce(
        viewsError?.statusCode || 200,
        viewsError?.data || [rawGridView]
      )

    mockServer.mock
      .onGet(`/database/fields/table/${table.id}/`)
      .replyOnce(fieldsError?.statusCode || 200, fieldsError?.data || rawFields)

    mockServer.mock
      .onGet(`database/views/grid/${rawGridView.id}/`)
      .replyOnce(rowsError?.statusCode || 200, rowsError?.data || rawRows)

    return { application, table, view: rawGridView }
  }
})
