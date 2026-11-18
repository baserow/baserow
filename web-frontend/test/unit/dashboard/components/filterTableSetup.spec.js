import { TestApp } from '@baserow/test/helpers/testApp'
import FilterTableSetup from '@baserow/modules/dashboard/components/widget/FilterTableSetup'

let testApp

beforeEach(() => {
  testApp = new TestApp()
})
afterEach(async () => {
  await testApp.afterEach()
  vi.restoreAllMocks()
})

const workspace = { id: 1 }

async function mountSetup({ widget = {}, tables = null } = {}) {
  const store = testApp.store
  store.commit('application/SET_ITEMS', [
    {
      id: 20,
      type: 'database',
      name: 'Sales',
      workspace,
      tables: tables || [
        { id: 6, name: 'Tickets' },
        { id: 1, name: 'Orders' },
      ],
    },
  ])
  store.commit('dashboardApplication/SET_DASHBOARD_ID', 1)
  const filter = {
    id: 2,
    type: 'text_filter',
    title: 'Filter',
    target_filters: [],
    filter_table_id: null,
    apply_to_new_widgets: false,
    ...widget,
  }
  store.commit('dashboardApplication/SET_WIDGETS', [
    filter,
    { id: 3, type: 'summary', title: 'Revenue', data_source_id: 4 },
  ])
  store.commit('dashboardApplication/SET_DATA_SOURCES', [
    { id: 4, table_id: 1, filters: [] },
  ])
  const get = vi.spyOn(store.$client, 'get')
  const save = vi.fn().mockResolvedValue(true)
  const wrapper = await testApp.mount(FilterTableSetup, {
    props: { widget: filter, dashboard: { id: 1, workspace }, save },
  })
  return { wrapper, save, get }
}

const tablePicker = (wrapper) => wrapper.findComponent({ name: 'Dropdown' })

test('offers the tables the dashboard shows first, without loading fields', async () => {
  const { wrapper, get } = await mountSetup()

  const items = tablePicker(wrapper).findAllComponents({ name: 'DropdownItem' })
  expect(items.map((item) => item.props('name'))).toEqual(['Orders', 'Tickets'])
  expect(items.map((item) => item.props('description'))).toEqual([
    'filterTableSetup.usedByWidgets - 1',
    'Sales',
  ])
  expect(wrapper.text()).toContain('filterTableSetup.question')
  // Only a table is asked: no field is offered or fetched.
  expect(wrapper.findAllComponents({ name: 'Dropdown' })).toHaveLength(1)
  expect(get).not.toHaveBeenCalled()
})

test('the first table also filters widgets added later', async () => {
  const { wrapper, save } = await mountSetup()

  await tablePicker(wrapper).vm.$emit('update:modelValue', 6)

  expect(save).toHaveBeenCalledWith({
    filter_table_id: 6,
    apply_to_new_widgets: true,
  })
})

test('changing the table keeps the choice about widgets added later', async () => {
  const { wrapper, save } = await mountSetup({
    widget: { filter_table_id: 1, apply_to_new_widgets: false },
  })
  expect(tablePicker(wrapper).props('modelValue')).toBe(1)
  expect(wrapper.text()).toContain('textFilterWidget.whatItFilters')

  await tablePicker(wrapper).vm.$emit('update:modelValue', 1)
  expect(save).not.toHaveBeenCalled()
  await tablePicker(wrapper).vm.$emit('update:modelValue', 6)

  expect(save).toHaveBeenCalledWith({ filter_table_id: 6 })
})

test('says to add a table when the workspace has none', async () => {
  const { wrapper } = await mountSetup({ tables: [] })

  expect(wrapper.text()).toContain('filterTableSetup.noTables')
  expect(tablePicker(wrapper).exists()).toBe(false)
})
