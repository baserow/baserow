import { TestApp } from '@baserow/test/helpers/testApp'
import { createStore } from 'vuex'
import { WidgetDataProviderType } from '@baserow/modules/dashboard/dataProviderTypes'
import { FilterWidgetType } from '@baserow/modules/dashboard/widgetTypes'
import dashboardApplication from '@baserow/modules/dashboard/store/dashboardApplication'

let testApp
beforeEach(() => {
  testApp = new TestApp()
})
afterEach(() => testApp.afterEach())

test('filter picker exposes titled strings from the selected dashboard store', async () => {
  const store = createStore({
    modules: {
      dashboardApplication,
      template: { namespaced: true, modules: { dashboardApplication } },
    },
  })
  store.$registry = testApp.store.$registry
  await store.dispatch('dashboardApplication/forceSetWidgets', [
    { id: 1, type: 'text_filter', title: 'Private', default_value: 'secret' },
  ])
  await store.dispatch('template/dashboardApplication/forceSetWidgets', [
    { id: 2, type: 'text_filter', title: 'Search', default_value: '' },
    { id: 3, type: 'summary', title: 'Total' },
  ])
  const provider = new WidgetDataProviderType({
    app: {
      $store: store,
      $registry: testApp.store.$registry,
      $i18n: { t: (key) => key },
    },
  })
  const context = { storePrefix: 'template/' }
  expect(provider.getNodes(context)).toMatchSnapshot()
  expect(provider.getDataSourceDispatchContext(context)).toEqual({ 2: '' })
  expect(provider.getDataChunk(context, ['2'])).toBe('')
  expect(provider.isValid(['2', 'extra'])).toBe(false)
})

test('the dynamic formula picker exposes only its owning input', () => {
  const store = createStore({ modules: { dashboardApplication } })
  store.commit('dashboardApplication/SET_WIDGETS', [
    { id: 1, type: 'text_filter', title: 'Owner' },
    { id: 2, type: 'text_filter', title: 'Another input' },
  ])
  const provider = new WidgetDataProviderType({
    app: { $store: store, $registry: testApp.store.$registry },
  })
  expect(provider.getDataSchema({ owningWidgetId: 1 })).toEqual({
    type: 'object',
    properties: { 1: { type: 'string', title: 'Owner' } },
  })
})

test('new filter types supply their own formula schema', () => {
  class NumberFilterWidgetType extends FilterWidgetType {
    static getType() {
      return 'number_filter'
    }
    get name() {
      return 'Number filter'
    }
    getValueSchema(widget) {
      return { type: 'number', title: widget.title }
    }
  }
  const registry = testApp.store.$registry
  registry.register(
    'dashboardWidget',
    new NumberFilterWidgetType({ app: testApp.app })
  )
  try {
    testApp.store.commit('dashboardApplication/SET_WIDGETS', [
      { id: 4, type: 'number_filter', title: 'Minimum' },
      { id: 5, type: 'summary', title: 'Total' },
    ])
    const provider = new WidgetDataProviderType({
      app: { $store: testApp.store, $registry: registry },
    })
    expect(provider.getDataSchema({})).toMatchSnapshot()
  } finally {
    registry.unregister('dashboardWidget', 'number_filter')
  }
})

test('dropdown option picker exposes each used table once in the selected dashboard', async () => {
  const { DashboardTableDataProviderType } =
    await import('@baserow/modules/dashboard/dataProviderTypes')
  const store = testApp.store
  const prefix = 'template/dashboardApplication/'
  const tableSchema = {
    title: 'Orders',
    type: 'array',
    items: {
      type: 'object',
      properties: { field_10: { type: 'string', title: 'Country' } },
    },
  }
  store.commit(prefix + 'SET_WIDGETS', [
    { id: 1, data_source_id: 2 },
    { id: 2, data_source_id: 3 },
    { id: 3, type: 'text_filter' },
  ])
  store.commit(prefix + 'SET_DATA_SOURCES', [
    { id: 2, table_id: 5, table_schema: tableSchema },
    { id: 3, table_id: 5, table_schema: tableSchema },
    { id: 4, table_id: 6, table_schema: tableSchema },
  ])
  const provider = new DashboardTableDataProviderType({
    app: { $store: store },
  })
  expect(provider.getDataSchema({ storePrefix: 'template/' })).toEqual({
    type: 'object',
    properties: { 5: { ...tableSchema, order: 0 } },
  })
  expect(provider.isValid(['5', '*', 'field_10'])).toBe(true)
  expect(provider.isValid(['5'])).toBe(false)
})
