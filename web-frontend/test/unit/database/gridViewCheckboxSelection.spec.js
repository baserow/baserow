import { TestApp } from '@baserow/test/helpers/testApp'
import GridView from '@baserow/modules/database/components/view/grid/GridView'
import GridViewRow from '@baserow/modules/database/components/view/grid/GridViewRow'

const baseMockConfig = {
  BASEROW_ROW_PAGE_SIZE_LIMIT: 200,
}

describe('GridView checkbox selection', () => {
  let testApp = null
  let mockServer = null
  let store = null

  beforeAll(() => {
    testApp = new TestApp()
    store = testApp.store
    mockServer = testApp.mockServer
  })

  beforeEach(() => {
    store.$config = { ...baseMockConfig }
  })

  afterEach((done) => {
    testApp.afterEach().then(done)
  })

  const mountComponent = (component, props, slots = {}) => {
    return testApp.mount(component, { propsData: props, slots })
  }

  const primary = {
    id: 1,
    name: 'Name',
    order: 0,
    type: 'text',
    primary: true,
    text_default: '',
    _: {
      loading: false,
    },
  }

  const fieldData = [
    {
      id: 2,
      name: 'Surname',
      type: 'text',
      text_default: '',
      primary: false,
      _: {
        loading: false,
        type: {
          iconClass: 'iconoir-text',
          name: 'text',
        },
      },
    },
  ]

  const rows = [
    {
      id: 1,
      order: '1.00000000000000000000',
      field_1: 'John',
      field_2: 'Doe',
      _: { selectedBy: [] },
    },
    {
      id: 2,
      order: '2.00000000000000000000',
      field_1: 'Jane',
      field_2: 'Smith',
      _: { selectedBy: [] },
    },
    {
      id: 3,
      order: '3.00000000000000000000',
      field_1: 'Bob',
      field_2: 'Johnson',
      _: { selectedBy: [] },
    },
    {
      id: 4,
      order: '4.00000000000000000000',
      field_1: 'Alice',
      field_2: 'Brown',
      _: { selectedBy: [] },
    },
    {
      id: 5,
      order: '5.00000000000000000000',
      field_1: 'Charlie',
      field_2: 'Wilson',
      _: { selectedBy: [] },
    },
  ]

  const populateStore = async () => {
    const table = mockServer.createTable()
    const { application } = await mockServer.createAppAndWorkspace(table)
    const view = mockServer.createGridView(application, table, {})
    const fields = mockServer.createFields(application, table, fieldData)

    mockServer.createGridRows(view, fields, rows)
    await store.dispatch('page/view/grid/fetchInitial', {
      gridId: 1,
      fields,
      primary,
    })
    await store.dispatch('view/fetchAll', { id: 1 })
    return { table, fields, view, application }
  }

  test('cannot select more than limit checkboxes', async () => {
    await populateStore()
    const limit = 3

    store.$config = {
      ...baseMockConfig,
      BASEROW_ROW_PAGE_SIZE_LIMIT: limit,
    }

    for (let i = 0; i < limit; i++) {
      await store.dispatch('page/view/grid/toggleCheckboxRowSelection', {
        row: rows[i],
      })
    }

    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', {
      row: rows[limit],
    })

    expect(store.state['page/view/grid'].checkboxSelectedRows.length).toBe(
      limit
    )

    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', {
      row: rows[0],
    })

    expect(store.state['page/view/grid'].checkboxSelectedRows.length).toBe(
      limit - 1
    )

    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', {
      row: rows[limit],
    })

    expect(store.state['page/view/grid'].checkboxSelectedRows.length).toBe(
      limit
    )
  })

  test('checkbox shows selected state', async () => {
    const { fields, view, application } = await populateStore()

    const row = rows[0]

    const wrapper = await mountComponent(GridViewRow, {
      view,
      renderedFields: fields,
      visibleFields: fields,
      allFieldsInTable: fields,
      leftOffset: 0,
      readOnly: false,
      includeRowDetails: true,
      storePrefix: 'page/',
      decorationsByPlace: {},
      rowsAtEndOfGroups: new Set(),
      workspaceId: application.workspace.id,
      count: 1,
      canDrag: true,
      rowIdentifierType: 'id',
      row,
      fieldWidths: { 1: 200, 2: 200 },
    })

    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', { row })
    store.commit('page/view/grid/SET_SELECTION_TYPE', 'checkbox')
    store.commit('page/view/grid/SET_MULTISELECT_ACTIVE', true)

    await wrapper.vm.$nextTick()

    expect(wrapper.find('.checkbox--checked').exists()).toBe(true)
  })

  test('different context menus for checked vs unchecked rows', async () => {
    const { table, fields, view, application } = await populateStore()
    const row = rows[0]
    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', { row })

    const wrapper = await mountComponent(GridView, {
      database: application,
      table,
      view,
      fields,
      readOnly: false,
      storePrefix: 'page/',
    })

    await wrapper.vm.$nextTick()

    await wrapper.vm.showRowContext({ preventDefault: () => {} }, row)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.$refs.rowContext).toBeTruthy()
    let firstMenu = wrapper.vm.$refs.rowContext.$el.querySelector(
      '.context__menu:first-child'
    )
    expect(firstMenu.style.display).not.toBe('none')
    let secondMenu = wrapper.vm.$refs.rowContext.$el.querySelector(
      '.context__menu:last-child'
    )
    expect(secondMenu.style.display).toBe('none')

    await store.dispatch('page/view/grid/clearAndDisableMultiSelect')

    await wrapper.vm.showRowContext({ preventDefault: () => {} }, row)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.$refs.rowContext).toBeTruthy()
    firstMenu = wrapper.vm.$refs.rowContext.$el.querySelector(
      '.context__menu:first-child'
    )
    expect(firstMenu.style.display).toBe('none')
    secondMenu = wrapper.vm.$refs.rowContext.$el.querySelector(
      '.context__menu:last-child'
    )
    expect(secondMenu.style.display).not.toBe('none')
  })

  test('clicking cell clears checkboxes', async () => {
    const { table, fields, view, application } = await populateStore()
    const row = rows[0]
    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', { row })

    const wrapper = await mountComponent(GridView, {
      database: application,
      table,
      view,
      fields,
      readOnly: false,
      storePrefix: 'page/',
    })

    await wrapper.vm.$nextTick()

    store.commit('page/view/grid/SET_SELECTION_TYPE', 'checkbox')
    store.commit('page/view/grid/SET_MULTISELECT_ACTIVE', true)

    await wrapper.vm.multiSelectStart({
      field: fields[0],
      row,
      event: { preventDefault: () => {} },
    })

    expect(store.state['page/view/grid'].checkboxSelectedRows.length).toBe(0)
  })

  test('copying selected rows works correctly', async () => {
    const { table, fields, view, application } = await populateStore()

    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', {
      row: rows[0],
    })
    await store.dispatch('page/view/grid/toggleCheckboxRowSelection', {
      row: rows[1],
    })

    const wrapper = await mountComponent(GridView, {
      database: application,
      table,
      view,
      fields,
      readOnly: false,
      storePrefix: 'page/',
    })

    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn(),
      },
    })

    await wrapper.vm.copySelection({ preventDefault: () => {} })

    expect(navigator.clipboard.writeText).toHaveBeenCalled()
  })
})
