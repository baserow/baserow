import { TestApp } from '@baserow/test/helpers/testApp'
import Table from '@baserow/modules/database/pages/table'
import {
  DEFAULT_VIEW_ID_COOKIE_NAME,
  readDefaultViewIdFromCookie,
  decodeDefaultViewIdPerTable,
  encodeDefaultViewIdPerTable,
} from '@baserow/modules/database/utils/view'
import gallery from '~/modules/database/services/view/gallery'
import { NuxtPage } from '#components'

// Mock out debounce so we don't have to wait or simulate waiting for the various
// debounces in the search functionality.
vi.mock('lodash/debounce', { default: () => vi.fn((fn) => fn) })

describe('View Tests', () => {
  let testApp = null
  let mockServer = null

  beforeEach(() => {
    testApp = new TestApp()
    mockServer = testApp.mockServer
  })

  afterEach(async () => await testApp.afterEach())

  const mountRoute = (route) => {
    // Let's mount a NuxtPage component for the route.
    // It allow the router to work properly
    const App = defineComponent({
      components: { NuxtPage },
      template: '<NuxtPage />',
    })

    return testApp.mount(App, {
      route,
    })
  }

  test('Default view is being set correctly initially', async () => {
    const { application, table, views } =
      await givenATableInTheServerWithMultipleViews()

    const gridView = views[0]
    const galleryView = views[1]

    const tableComponent = await mountRoute(
      `/database/${application.id}/table/${table.id}/${galleryView.id}?token=fake`
    )

    const tableId = gridView.table_id

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    // Check if cookie is updated correctly (default view):
    const defaultViewId = readDefaultViewIdFromCookie(tableId)
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
    const tableComponent = await mountRoute(
      `/database/${application.id}/table/${table.id}/${galleryView.id}?token=fake`
    )

    const tableId = gridView.table_id

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    // Check if cookie is updated correctly (default view):
    const defaultViewId = readDefaultViewIdFromCookie(tableId)
    expect(defaultViewId).toEqual(galleryView.id)

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

    await nextTick()

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    const updatedDefaultViewId = readDefaultViewIdFromCookie(tableId)
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
    const firstTableComponent = await mountRoute(
      `/database/${application.id}/table/${firstTable.id}/?token=fake`
    )

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(firstTableGridView.id)
    // Check if cookie is updated correctly (default view):
    const defaultViewId = readDefaultViewIdFromCookie(
      firstTableGridView.table_id
    )
    const defaultView = testApp.store.getters['view/get'](defaultViewId)
    expect(defaultViewId).toEqual(firstTableGridView.id)
    expect(defaultView.table_id).toBe(firstTableGridView.table_id)
    expect(defaultView.id).toBe(firstTableGridView.id)

    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(firstTableGridView.id)
    // Check if component is rendered:
    expect(firstTableComponent.find('div.grid-view').exists()).toBe(true)
    expect(firstTableComponent.find('div.gallery-view').exists()).toBe(false)

    await firstTableComponent.unmount()

    // The first (and default) view is the Grid view, which is going to be rendered
    // initially for the secondTable:
    const secondTableComponent = await mountRoute(
      `/database/${application.id}/table/${secondTable.id}/?token=fake`
    )

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(secondTableGridView.id)
    const defaultViewIdAfterChangingTable = readDefaultViewIdFromCookie(
      secondTableGridView.table_id
    )
    expect(defaultViewIdAfterChangingTable).toEqual(secondTableGridView.id)
    const defaultViewAfterChangingTable = testApp.store.getters['view/get'](
      defaultViewIdAfterChangingTable
    )
    expect(defaultViewAfterChangingTable.table_id).toBe(
      secondTableGridView.table_id
    )
    expect(defaultViewAfterChangingTable.id).toBe(secondTableGridView.id)
    // Check if Vuex store is updated correctly (default view):
    expect(testApp.store.getters['view/defaultId']).toBe(secondTableGridView.id)

    await secondTableComponent.unmount()
    // Let's switch back to the first table in the database and see if first table's
    // default view is appended to the *end* of remembered views array:
    await mountRoute(
      `/database/${application.id}/table/${firstTable.id}/?token=fake`
    )

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(firstTableGridView.id)
    const defaultViewIdAfterSwitchingBack = readDefaultViewIdFromCookie(
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

    // Set the cookie for defaultView manually:
    const defaultViewIdData = [
      {
        tableId: galleryView.table_id,
        viewId: galleryView.id,
      },
    ]

    const cookie = useCookie(DEFAULT_VIEW_ID_COOKIE_NAME, {
      path: '/',
    })
    cookie.value = encodeDefaultViewIdPerTable(defaultViewIdData)
    await nextTick() // Let the cookie to be written

    // The first view is the Grid view, the Default view is the Gallery view,
    // we're not rendering any view initially and Default view (Gallery view)
    // should be picked up from the cookie
    const tableComponent = await mountRoute(
      `/database/${application.id}/table/${table.id}/?token=fake`
    )

    // Check if Vuex store is updated correctly (first view):
    expect(testApp.store.getters['view/first'].id).toBe(gridView.id)
    const defaultViewId = readDefaultViewIdFromCookie(tableId)
    expect(defaultViewId).toEqual(galleryView.id)
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
    const cookie = useCookie(DEFAULT_VIEW_ID_COOKIE_NAME, {
      path: '/',
    })
    cookie.value = encodeDefaultViewIdPerTable(randomData)
    await nextTick() // Let the cookie to be written

    const originalDataLength = randomData.length

    // Mount the component, which should update the cookies
    await mountRoute(
      `/database/${application.id}/table/${table.id}/${gridView.id}?token=fake`
    )

    // The Default view is the Grid view and it should be set (appended) in the cookie
    await nextTick()
    const cookieValue = decodeDefaultViewIdPerTable(cookie.value)
    expect(cookieValue.length).toBeGreaterThan(0)

    const defaultViewIdObject = cookieValue[cookieValue.length - 1]
    expect(defaultViewIdObject.tableId).toBe(gridView.table_id)
    expect(defaultViewIdObject.viewId).toBe(gridView.id)

    // Check if gridView is set as the last view in the array
    expect(cookieValue[cookieValue.length - 1]).toMatchObject(
      defaultViewIdObject
    )

    // Ensure that the first element is removed from the cookie array
    const updatedCookieValue = decodeDefaultViewIdPerTable(cookie.value)
    expect(updatedCookieValue).not.toContainEqual(randomData[0])
    expect(updatedCookieValue.length).toBeLessThan(originalDataLength)
  })

  test('Unknown error during views loading is displayed correctly - no view toolbar', async () => {
    const viewsError = { statusCode: 500, data: 'some backend error' }

    // no list of views
    const { application, table } = await givenATableWithError({
      viewsError,
    })

    await expect(
      testApp.mount(Table, {
        route: `/database/${application.id}/table/${table.id}/123?token=fake`,
      })
    ).rejects.toThrow('Request failed with status code 500')
  })

  test.skip('API error during views loading is displayed correctly', async () => {
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

    await expect(
      testApp.mount(Table, {
        route: `/database/${application.id}/table/${table.id}/123?token=fake`,
      })
    ).rejects.toThrow('Request failed with status code 400')
  })

  test.skip('API error during view rows loading', async () => {
    const rowsError = { statusCode: 500, data: { message: 'Unknown error' } }
    const errorHandler = vi.fn()

    // views list readable, fields readable, rows not readable
    const { application, table, view } = await givenATableWithError({
      rowsError,
    })

    const tableComponent = await testApp.mount(Table, {
      route: `/database/${application.id}/table/${table.id}/${view.id}?token=fake`,
      global: {
        config: {
          errorHandler,
        },
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
    mockServer.fakeSettings()
    mockServer.fakeAuthentication()

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
    mockServer.fakeSettings()
    mockServer.fakeAuthentication()

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
    mockServer.fakeSettings()
    mockServer.fakeJobs()
    mockServer.fakeAuthentication()

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
