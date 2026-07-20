import { flushPromises } from '@vue/test-utils'

import { TestApp } from '@baserow/test/helpers/testApp'
import SelectRowContent from '@baserow/modules/database/components/row/SelectRowContent'
import RowService from '@baserow/modules/database/services/row'
import FieldService from '@baserow/modules/database/services/field'
import ViewService from '@baserow/modules/database/services/view'

vi.mock('@baserow/modules/database/services/row', () => ({
  default: vi.fn(),
}))

vi.mock('@baserow/modules/database/services/field', () => ({
  default: vi.fn(),
}))

vi.mock('@baserow/modules/database/services/view', () => ({
  default: vi.fn(),
}))

vi.mock('@baserow/modules/core/utils/indexedDB', () => ({
  getData: vi.fn().mockResolvedValue(null),
  setData: vi.fn().mockResolvedValue(undefined),
}))

const TABLE_ID = 758
const LINKED_TABLE_ID = 755
const PRIMARY_FIELD = {
  id: 100,
  table_id: TABLE_ID,
  name: 'Name',
  type: 'text',
  primary: true,
  text_default: '',
  _: { loading: false },
}
const SECONDARY_FIELD = {
  id: 101,
  table_id: TABLE_ID,
  name: 'Email',
  type: 'text',
  primary: false,
  text_default: '',
  _: { loading: false },
}

function setupServiceMocks() {
  const createFn = vi.fn()
  const fetchAllRows = vi.fn().mockResolvedValue({
    data: { count: 0, results: [], next: null, previous: null },
  })
  RowService.mockReturnValue({ create: createFn, fetchAll: fetchAllRows })

  FieldService.mockReturnValue({
    fetchAll: vi.fn().mockResolvedValue({
      data: [{ ...PRIMARY_FIELD }, { ...SECONDARY_FIELD }],
    }),
  })

  ViewService.mockReturnValue({
    fetchAll: vi.fn().mockResolvedValue({ data: [] }),
    fetchFieldOptions: vi
      .fn()
      .mockResolvedValue({ data: { field_options: {} } }),
  })

  return { createFn, fetchAllRows }
}

describe('SelectRowContent', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
    vi.restoreAllMocks()
  })

  function setupStoreWithDatabase({ withView = false } = {}) {
    const store = testApp.getStore()
    store.commit('application/SET_ITEMS', [
      {
        id: 1,
        type: 'database',
        workspace: { id: 1 },
        tables: [{ id: TABLE_ID, name: 'Team members' }],
      },
    ])
    if (withView) {
      store.state.view.selected = {
        id: 3387,
        type: 'grid',
        table_id: LINKED_TABLE_ID,
      }
    } else {
      store.state.view.selected = { id: 0 }
    }
  }

  async function mountContent(valueArray = []) {
    const wrapper = await testApp.mount(SelectRowContent, {
      props: {
        tableId: TABLE_ID,
        value: valueArray,
        multiple: true,
      },
      global: {
        stubs: {
          RowCreateModal: true,
          SimpleGrid: true,
          ViewFieldsContext: true,
          Paginator: true,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  test('select() toggles existing row to unselected in multiple mode', async () => {
    setupStoreWithDatabase()
    setupServiceMocks()

    const wrapper = await mountContent([{ id: 42, value: 'Existing' }])

    wrapper.vm.select({ id: 42 })

    const events = wrapper.emitted()
    expect(events.unselected).toHaveLength(1)
    expect(events.unselected[0][0].row.id).toBe(42)
    expect(events.selected).toBeUndefined()
  })

  test('select() emits selected for new row in multiple mode', async () => {
    setupStoreWithDatabase()
    setupServiceMocks()

    const wrapper = await mountContent([])

    wrapper.vm.select({ id: 42 })

    const events = wrapper.emitted()
    expect(events.selected).toHaveLength(1)
    expect(events.selected[0][0].row.id).toBe(42)
    expect(events.unselected).toBeUndefined()
  })

  test('createRow does not unselect when WebSocket already added row to value', async () => {
    setupStoreWithDatabase({ withView: true })
    const { createFn, fetchAllRows } = setupServiceMocks()

    const createdRowId = 99
    createFn.mockResolvedValue({
      data: { id: createdRowId, field_100: 'New Member', field_101: '' },
    })
    fetchAllRows.mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: [{ id: createdRowId, field_100: 'New Member', field_101: '' }],
      },
    })

    // Mount with value already containing the new row — simulates WebSocket
    // having delivered rows_updated before createRow finishes.
    const wrapper = await mountContent([
      { id: createdRowId, value: 'New Member' },
    ])

    const callback = vi.fn()
    await wrapper.vm.createRow({
      row: { field_100: 'New Member' },
      callback,
    })
    await flushPromises()

    expect(callback).toHaveBeenCalledTimes(1)

    const events = wrapper.emitted()
    // Must NOT emit 'unselected' — that's the bug
    expect(events.unselected).toBeUndefined()
    // Should NOT emit 'selected' either — row is already linked via WebSocket
    expect(events.selected).toBeUndefined()
  })

  test('createRow emits selected when WebSocket has not yet arrived', async () => {
    setupStoreWithDatabase({ withView: true })
    const { createFn, fetchAllRows } = setupServiceMocks()

    const createdRowId = 99
    createFn.mockResolvedValue({
      data: { id: createdRowId, field_100: 'New Member', field_101: '' },
    })
    fetchAllRows.mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: [{ id: createdRowId, field_100: 'New Member', field_101: '' }],
      },
    })

    // Mount with empty value — WebSocket hasn't arrived yet
    const wrapper = await mountContent([])

    const callback = vi.fn()
    await wrapper.vm.createRow({
      row: { field_100: 'New Member' },
      callback,
    })
    await flushPromises()

    expect(callback).toHaveBeenCalledTimes(1)

    const events = wrapper.emitted()
    // Must emit 'selected' to link the row
    expect(events.selected).toHaveLength(1)
    expect(events.selected[0][0].row.id).toBe(createdRowId)
    // Must NOT emit 'unselected'
    expect(events.unselected).toBeUndefined()
  })
})
