import KanbanView from '@baserow_premium/components/views/kanban/KanbanView.vue'
import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import InfiniteScroll from '@baserow/modules/core/components/helpers/InfiniteScroll.vue'
import KanbanViewStack from '@baserow_premium/components/views/kanban/KanbanViewStack.vue'
import RowCard from '@baserow/modules/database/components/card/RowCard.vue'
import flushPromises from 'flush-promises'

describe('KanbanView component', () => {
  let testApp = null
  let mockServer = null
  let store = null

  beforeAll(() => {
    testApp = new PremiumTestApp(null)
    testApp.giveCurrentUserGlobalPremiumFeatures()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  afterEach((done) => {
    testApp.afterEach().then(done)
  })

  const mountComponent = (props, slots = {}) => {
    return testApp.mount(KanbanView, { propsData: props, slots })
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
  const selectOption1 = {
    id: 1,
    value: 'Blue color',
    color: 'blue',
  }

  const fieldData = [
    primary,
    {
      id: 2,
      name: 'Options',
      order: 1,
      primary: false,
      type: 'single_select',
      related_fields: [],
      select_options: [selectOption1],
      _: {
        type: {
          type: 'single_select',
          iconClass: 'baserow-icon-single-select',
          name: 'Single select',
          isReadOnly: false,
          canImport: true,
        },
        loading: false,
      },
    },
  ]

  const rows = [
    { id: 2, order: '2.00', field_1: '2nd field text', field_2: null },
    { id: 4, order: '2.50', field_1: '4th field text', field_2: selectOption1 },
    { id: 3, order: '3.00', field_1: '3rd field text', field_2: selectOption1 },
    { id: 6, order: '7.00', field_1: '6th field text', field_2: selectOption1 },
  ]

  const populateStore = async () => {
    const table = mockServer.createTable()
    const { application } = await mockServer.createAppAndWorkspace(table)
    const view = mockServer.createKanbanView(application, table, {
      singleSelectFieldId: 2,
    })

    const fields = mockServer.createFields(application, table, fieldData)

    const stacks = {
      null: {
        count: 1,
        results: [rows[0]],
      },
      1: {
        count: 2,
        results: [rows[1], rows[2], rows[3]],
      },
    }

    mockServer.thereAreRowsInKanbanView(
      { 2: { hidden: false, order: 1 } },
      stacks
    )

    await store.dispatch('page/view/kanban/fetchInitial', {
      kanbanId: 5,
      singleSelectFieldId: 2,
    })

    return { table, fields, view, application }
  }

  test('KanbanView allows deleting row with context menu', async () => {
    const { table, fields, view, application } = await populateStore()

    expect(store.getters['page/view/kanban/getSingleSelectFieldId']).toBe(2)

    // InfiniteScroll can't set properly clientHeight, and it's always 0
    // so this mock will overwrite clientHeight
    InfiniteScroll.methods.clientHeight = jest.fn().mockReturnValue(5000)

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
    })
    expect(wrapper.element).toMatchSnapshot()
    const mockEventHandler = jest.spyOn(wrapper.vm, 'showRowContext')
    const mockDeleteRowHandler = jest.spyOn(wrapper.vm, 'deleteRow')

    const kanbanStackWrapper = wrapper.findComponent(KanbanViewStack)
    const rowCardWrapper = kanbanStackWrapper.findComponent(RowCard)
    const mockEvent = { preventDefault: jest.fn() }
    rowCardWrapper.trigger('contextmenu', { row: rows[0], event: mockEvent })

    await wrapper.vm.$nextTick()

    expect(mockEventHandler).toHaveBeenCalled()
    expect(mockEventHandler.mock.calls[0][0].row).toEqual(rows[0])

    expect(store.getters['page/view/kanban/getStack']('null').count).toBe(1)
    mockServer.deleteGridRow(table.id, rows[0].id)
    const ctx = wrapper.find('.js-ctx-delete-row')
    ctx.trigger('click')

    await wrapper.vm.$nextTick()

    expect(mockDeleteRowHandler).toHaveBeenCalled()

    const expectedRow = {
      ...rows[0],
      _: {
        metadata: {},
        dragging: false,
        loading: true,
        fetching: false,
        fullyLoaded: false,
      },
    }
    expect(mockDeleteRowHandler.mock.calls[0][0]).toEqual(expectedRow)

    await wrapper.vm.$nextTick()
    expect(store.getters['page/view/kanban/getStack']('null').count).toBe(0)
  })

  test('KanbanView row is restored when server fails to delete it', async () => {
    const { table, fields, view, application } = await populateStore()

    expect(store.getters['page/view/kanban/getSingleSelectFieldId']).toBe(2)

    // InfiniteScroll can't set properly clientHeight, and it's always 0
    // so this mock will overwrite clientHeight
    InfiniteScroll.methods.clientHeight = jest.fn().mockReturnValue(5000)

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
    })
    const mockEventHandler = jest.spyOn(wrapper.vm, 'showRowContext')
    const mockDeleteRowHandler = jest.spyOn(wrapper.vm, 'deleteRow')

    const kanbanStackWrapper = wrapper.findComponent(KanbanViewStack)
    const rowCardWrapper = kanbanStackWrapper.findComponent(RowCard)
    const mockEvent = { preventDefault: jest.fn() }
    rowCardWrapper.trigger('contextmenu', { row: rows[0], event: mockEvent })

    await wrapper.vm.$nextTick()

    expect(mockEventHandler).toHaveBeenCalled()
    expect(mockEventHandler.mock.calls[0][0].row).toEqual(rows[0])

    expect(store.getters['page/view/kanban/getStack']('null').count).toBe(1)

    testApp.dontFailOnErrorResponses()
    mockServer.deleteGridRow(table.id, rows[0].id, 400)
    const ctx = wrapper.find('.js-ctx-delete-row')
    ctx.trigger('click')

    await wrapper.vm.$nextTick()

    expect(mockDeleteRowHandler).toHaveBeenCalled()

    const expectedRow = {
      ...rows[0],
      _: {
        metadata: {},
        dragging: false,
        loading: true,
        fetching: false,
        fullyLoaded: false,
      },
    }
    expect(mockDeleteRowHandler.mock.calls[0][0]).toEqual(expectedRow)

    await flushPromises()
    await wrapper.vm.$nextTick()

    expect(store.getters['page/view/kanban/getStack']('null').count).toBe(1)
  })
})
