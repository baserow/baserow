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

test('multiple filter values expose an array and support whole-list and index paths', async () => {
  const store = testApp.store
  await store.dispatch('dashboardApplication/forceSetWidgets', [
    {
      id: 1,
      type: 'text_filter',
      title: 'Country',
      mode: 'dropdown',
      multiple: true,
      default_value: 'France',
    },
  ])
  const provider = new WidgetDataProviderType({
    app: { $store: store, $registry: store.$registry },
  })
  expect(provider.getDataSchema({}).properties[1]).toEqual({
    type: 'array',
    title: 'Country',
    items: { type: 'string' },
  })
  expect(provider.getDataChunk({}, ['1', '*'])).toEqual(['France'])
  expect(provider.getDataChunk({}, ['1', '0'])).toBe('France')
  expect(provider.isValid(['1', '*'])).toBe(true)
  expect(provider.isValid(['1', '0'])).toBe(true)
  expect(provider.isValid(['1', '0', 'extra'])).toBe(false)
  store.commit('dashboardApplication/RESET')
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

test('dropdown options expose source metadata in the selected dashboard', async () => {
  const { DashboardDataSourceContextDataProviderType } =
    await import('@baserow/modules/dashboard/dataProviderTypes')
  const store = testApp.store
  const contextSchema = {
    type: 'object',
    title: 'Sales orders',
    properties: {
      field_10: {
        type: 'array',
        title: 'Region',
        items: {
          type: 'object',
          properties: {
            id: { type: 'number' },
            value: { type: 'string' },
            color: { type: 'string' },
          },
        },
      },
    },
  }
  store.commit('template/dashboardApplication/SET_DATA_SOURCES', [
    {
      id: 2,
      table_id: 114,
      type: 'local_baserow_list_rows',
      name: 'Orders',
      context_data_schema: contextSchema,
      context_data: { field_10: [{ value: 'Europe' }, { value: 'Americas' }] },
    },
    {
      id: 3,
      table_id: 114,
      type: 'local_baserow_list_rows',
      name: 'Revenue',
      context_data_schema: contextSchema,
    },
    {
      id: 4,
      type: 'local_baserow_aggregate_rows',
      name: 'Summary context',
      context_data_schema: null,
      context_data: {
        field: { id: 10, name: 'Revenue', number_decimal_places: 2 },
      },
    },
    {
      id: 5,
      name: 'Empty source',
      context_data: {},
      context_data_schema: null,
    },
    {
      id: 6,
      name: 'Chart context',
      context_data_schema: null,
      context_data: {
        fields: {
          field_10: { name: 'Region', select_options: [{ value: 'Europe' }] },
        },
      },
    },
  ])
  const provider = new DashboardDataSourceContextDataProviderType({
    app: {
      $store: store,
      $registry: store.$registry,
      $i18n: { t: (key) => key },
    },
  })
  const context = { storePrefix: 'template/' }
  expect(provider.getNodes(context)).toMatchSnapshot()
  expect(
    provider.getDataChunk(context, ['2', 'field_10', '*', 'value'])
  ).toEqual(['Europe', 'Americas'])
  expect(provider.getDataSchema({})).toEqual({ type: 'object', properties: {} })
  expect(provider.isValid(['2', 'field_10', '*', 'value'])).toBe(true)
  expect(provider.isValid(['2'])).toBe(false)
  expect(provider.isValid(['invalid', 'field_10'])).toBe(false)
})
