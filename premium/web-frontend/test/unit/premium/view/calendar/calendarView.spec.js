import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import CalendarView from '@baserow_premium/components/views/calendar/CalendarView.vue'
import CalendarMonthDay from '@baserow_premium/components/views/calendar/CalendarMonthDay.vue'
import CalendarCard from '@baserow_premium/components/views/calendar/CalendarCard.vue'

describe('CalendarView component', () => {
  let testApp = null
  let mockServer = null
  let store = null
  const originalDateNow = Date.now

  beforeAll(() => {
    testApp = new PremiumTestApp(null)
    testApp.giveCurrentUserGlobalPremiumFeatures()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach((done) => {
    testApp.afterEach().then(done)
    Date.now = originalDateNow
  })

  const mountComponent = (props, slots = {}) => {
    return testApp.mount(CalendarView, { propsData: props, slots })
  }

  const primary = {
    id: 1,
    name: 'Name',
    order: 0,
    type: 'text',
    primary: true,
    read_only: false,
    text_default: '',
    _: {
      type: {
        type: 'text',
        iconClass: 'iconoir-text',
        name: 'Single line text',
        isReadOnly: false,
        canImport: true,
      },
      loading: false,
    },
  }

  const dateField = {
    id: 2,
    name: 'Date',
    order: 1,
    type: 'date',
    primary: false,
    read_only: false,
    description: null,
    date_format: 'EU',
    date_include_time: false,
    date_time_format: '24',
    date_show_tzinfo: false,
    date_force_timezone: null,
  }

  const fieldData = [primary, dateField]

  const rows = [
    { id: 2, order: '2.00', field_1: '1nd field text', field_2: '2024-07-01' },
    { id: 4, order: '2.50', field_1: '3th field text', field_2: '2024-07-04' },
    { id: 3, order: '3.00', field_1: '2rd field text', field_2: '2024-07-04' },
  ]

  const populateStore = async () => {
    const table = mockServer.createTable()
    const { application } = await mockServer.createAppAndWorkspace(table)
    const view = mockServer.createCalendarView(application, table, {
      singleSelectFieldId: 2,
    })

    const fields = mockServer.createFields(application, table, fieldData)

    const calendarRecords = {
      '2024-07-01': { count: 1, results: [rows[0]] },
      '2024-07-04': { count: 2, results: [rows[1], rows[2]] },
    }

    mockServer.thereAreRowsInCalendarView(
      { 2: { hidden: false, order: 1 } },
      calendarRecords
    )

    store.commit('page/view/calendar/SET_SELECTED_DATE', new Date('2024-07-01'))
    store.commit('page/view/calendar/SET_DATE_FIELD_ID', dateField.id)
    await store.dispatch('page/view/calendar/fetchInitial', { fields })

    return { table, fields, view, application }
  }

  test('CalendarView allows deleting row with context menu', async () => {
    const { table, fields, view, application } = await populateStore()

    // CalendarMonthDay can't set properly clientHeight, and it's always 0
    // so this mock will overwrite clientHeight
    CalendarMonthDay.methods.getClientHeight = jest.fn().mockReturnValue(5000)
    Date.now = jest.fn(() => new Date('2024-07-05T12:00:00.000Z'))

    const wrapper = await mountComponent({
      view,
      database: {
        id: application.id,
        name: 'testing db',
        order: 1,
        group: {
          id: 210,
          name: "test's workspace",
          generative_ai_models_enabled: {},
        },
        workspace: application.workspace,
        tables: [table],
        type: 'database',
        _: {
          type: {
            type: 'database',
            iconClass: 'iconoir-db',
            name: 'Database',
            hasSidebarComponent: true,
          },
          loading: false,
          selected: true,
        },
      },
      table,
      fields,
      readOnly: false,
      storePrefix: 'page/',
      loading: false,
    })
    expect(wrapper.element).toMatchSnapshot()
    const mockEventHandler = jest.spyOn(wrapper.vm, 'showRowContext')
    const mockDeleteRowHandler = jest.spyOn(wrapper.vm, 'deleteRow')

    const calendarCardWrapper = wrapper.findComponent(CalendarCard)

    const mockEvent = { preventDefault: jest.fn() }
    calendarCardWrapper.trigger('contextmenu', {
      row: rows[0],
      event: mockEvent,
    })

    await wrapper.vm.$nextTick()

    expect(mockEventHandler).toHaveBeenCalled()
    expect(mockEventHandler.mock.calls[0][0].row).toEqual(rows[0])

    expect(
      store.getters['page/view/calendar/getDateStack']('2024-07-01').count
    ).toBe(1)
    mockServer.deleteGridRow(table.id, rows[0].id)
    const ctx = wrapper.find('.js-ctx-delete-row')
    ctx.trigger('click')

    await wrapper.vm.$nextTick()
    expect(mockDeleteRowHandler).toHaveBeenCalled()
    //
    const expectedRow = {
      ...rows[0],
      _: {
        metadata: {},
        matchSearch: true,
        fieldSearchMatches: [],
        loading: true,
        fetching: false,
        fullyLoaded: false,
      },
    }
    expect(mockDeleteRowHandler.mock.calls[0][0]).toEqual(expectedRow)
    await wrapper.vm.$nextTick()

    expect(
      store.getters['page/view/calendar/getDateStack']('2024-07-01').count
    ).toBe(0)
  })

  test('CalendarView row is restored when server fails to delete it', async () => {
    const { table, fields, view, application } = await populateStore()

    // CalendarMonthDay can't set properly clientHeight, and it's always 0
    // so this mock will overwrite clientHeight
    CalendarMonthDay.methods.getClientHeight = jest.fn().mockReturnValue(5000)
    Date.now = jest.fn(() => new Date('2024-07-05T12:00:00.000Z'))

    const wrapper = await mountComponent({
      view,
      database: {
        id: application.id,
        name: 'testing db',
        order: 1,
        group: {
          id: 210,
          name: "test's workspace",
          generative_ai_models_enabled: {},
        },
        workspace: application.workspace,
        tables: [table],
        type: 'database',
        _: {
          type: {
            type: 'database',
            iconClass: 'iconoir-db',
            name: 'Database',
            hasSidebarComponent: true,
          },
          loading: false,
          selected: true,
        },
      },
      table,
      fields,
      readOnly: false,
      storePrefix: 'page/',
      loading: false,
    })
    expect(wrapper.element).toMatchSnapshot()
    const mockEventHandler = jest.spyOn(wrapper.vm, 'showRowContext')
    const mockDeleteRowHandler = jest.spyOn(wrapper.vm, 'deleteRow')

    const calendarCardWrapper = wrapper.findComponent(CalendarCard)

    const mockEvent = { preventDefault: jest.fn() }
    calendarCardWrapper.trigger('contextmenu', {
      row: rows[0],
      event: mockEvent,
    })

    await wrapper.vm.$nextTick()

    expect(mockEventHandler).toHaveBeenCalled()
    expect(mockEventHandler.mock.calls[0][0].row).toEqual(rows[0])

    expect(
      store.getters['page/view/calendar/getDateStack']('2024-07-01').count
    ).toBe(1)

    testApp.dontFailOnErrorResponses()
    mockServer.deleteGridRow(table.id, rows[0].id)
    const ctx = wrapper.find('.js-ctx-delete-row')
    ctx.trigger('click')

    await wrapper.vm.$nextTick()
    expect(mockDeleteRowHandler).toHaveBeenCalled()

    const expectedRow = {
      ...rows[0],
      _: {
        metadata: {},
        matchSearch: true,
        fieldSearchMatches: [],
        loading: true,
        fetching: false,
        fullyLoaded: false,
      },
    }
    expect(mockDeleteRowHandler.mock.calls[0][0]).toEqual(expectedRow)
    await wrapper.vm.$nextTick()

    expect(
      store.getters['page/view/calendar/getDateStack']('2024-07-01').count
    ).toBe(0)
  })
})
