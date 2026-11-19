import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import ConfigureFilterTargetModal from '@baserow/modules/dashboard/components/widget/ConfigureFilterTargetModal'

let testApp
let validate
beforeEach(() => {
  testApp = new TestApp()
  validate = vi.fn(() => true)
})
afterEach(async () => {
  await testApp.afterEach()
  vi.restoreAllMocks()
})

async function mountConfiguration() {
  testApp.store.registerModule('guideddashboardApplication', {
    namespaced: true,
    getters: {
      getWidgets: () => [{ id: 30, type: 'summary', data_source_id: 31 }],
    },
    actions: {
      updateWidget: (_, { work }) => work,
      updateDataSource: (_, { work }) => work,
    },
  })
  return testApp.mount(ConfigureFilterTargetModal, {
    props: { dashboard: { id: 1 }, widgetId: 30, storePrefix: 'guided' },
    global: {
      stubs: {
        Modal: {
          template: '<div><slot /></div>',
          methods: { show() {}, hide() {} },
        },
        WidgetSettings: {
          template: '<div />',
          methods: { validate: () => validate() },
        },
      },
    },
  })
}
const submitButton = (wrapper) =>
  wrapper
    .findAll('button')
    .find((button) => button.text() === 'textFilterWidget.addToFilter')

/** Control completion of an ordinary settings save without timing assumptions. */
function deferred() {
  let resolve, reject
  const work = new Promise((done, fail) => {
    resolve = done
    reject = fail
  })
  return { work, resolve, reject }
}

test('returns the configured widget only after validation succeeds', async () => {
  const wrapper = await mountConfiguration()
  validate.mockReturnValue(false)
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toBeUndefined()
  validate.mockReturnValue(true)
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')[0]).toEqual([
    { id: 30, type: 'summary', data_source_id: 31 },
  ])
})

test('waits for every pending save for the configured widget', async () => {
  const wrapper = await mountConfiguration()
  const title = deferred()
  const source = deferred()
  const first = testApp.store.dispatch(
    'guideddashboardApplication/updateWidget',
    { widgetId: 30, work: title.work }
  )
  const second = testApp.store.dispatch(
    'guideddashboardApplication/updateDataSource',
    { dataSourceId: 31, work: source.work }
  )
  await flushPromises()
  expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
  title.resolve()
  await first
  await flushPromises()
  expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
  source.resolve()
  await second
  await flushPromises()
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toHaveLength(1)
})

test('keeps failed saves visible until that setting is saved successfully', async () => {
  const wrapper = await mountConfiguration()
  const save = deferred()
  const result = testApp.store
    .dispatch('guideddashboardApplication/updateDataSource', {
      dataSourceId: 31,
      work: save.work,
    })
    .catch(() => {})
  save.reject(new Error('Unavailable'))
  await result
  await flushPromises()
  expect(wrapper.text()).toContain('textFilterWidget.configurationSaveFailed')
  expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
  await testApp.store.dispatch('guideddashboardApplication/updateDataSource', {
    dataSourceId: 31,
    work: Promise.resolve(),
  })
  await flushPromises()
  expect(wrapper.text()).not.toContain(
    'textFilterWidget.configurationSaveFailed'
  )
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toHaveLength(1)
})

test('ignores saves for other widgets', async () => {
  const wrapper = await mountConfiguration()
  const save = deferred()
  const result = testApp.store.dispatch(
    'guideddashboardApplication/updateWidget',
    { widgetId: 99, work: save.work }
  )
  await flushPromises()
  expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
  save.resolve()
  await result
})

test('uses the real summary settings to require a table before completion', async () => {
  const widget = {
    id: 30,
    type: 'summary',
    title: 'Summary',
    description: '',
    data_source_id: 31,
  }
  testApp.store.commit('dashboardApplication/SET_WIDGETS', [widget])
  testApp.store.commit('dashboardApplication/SET_DATA_SOURCES', [
    {
      id: 31,
      type: 'local_baserow_aggregate_rows',
      integration_id: 10,
      table_id: null,
      field_id: null,
      aggregation_type: '',
      view_id: null,
      filters: [],
      filter_groups: [],
      filter_type: 'AND',
    },
  ])
  testApp.store.commit('dashboardApplication/ADD_INTEGRATION', {
    id: 10,
    context_data: {
      databases: [
        {
          id: 1,
          name: 'Database',
          tables: [{ id: 2, name: 'Rows' }],
          views: [],
        },
      ],
    },
  })
  vi.spyOn(testApp.store.$client, 'get').mockResolvedValue({
    data: [
      {
        id: 3,
        name: 'Amount',
        type: 'number',
        table_id: 2,
        number_decimal_places: 0,
      },
    ],
  })
  const dispatch = vi.spyOn(testApp.store, 'dispatch').mockResolvedValue()
  const wrapper = await testApp.mount(ConfigureFilterTargetModal, {
    props: { dashboard: { id: 1 }, widgetId: 30, excludeFilterWidgetId: 2 },
    global: {
      stubs: {
        Modal: {
          template: '<div><slot /></div>',
          methods: { show() {}, hide() {} },
        },
      },
    },
  })
  await flushPromises()
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toBeUndefined()
  wrapper
    .findComponent({ name: 'DashboardTableSelector' })
    .vm.$emit('update:modelValue', 2)
  await flushPromises()
  expect(dispatch).toHaveBeenCalledWith(
    'dashboardApplication/updateDataSource',
    expect.objectContaining({
      dataSourceId: 31,
      excludeFilterWidgetId: 2,
    })
  )
  testApp.store.commit('dashboardApplication/UPDATE_DATA_SOURCE', {
    dataSourceId: 31,
    values: {
      table_id: 2,
      field_id: 3,
      aggregation_type: 'sum',
    },
  })
  await flushPromises()
  expect(wrapper.find('.service-form__filter-buttons').exists()).toBe(false)
  expect(wrapper.find('.service-form__condition-form-tab').exists()).toBe(true)
  expect(wrapper.text()).toContain(
    'localBaserowTableServiceConditionalForm.noFilterTitle'
  )
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toHaveLength(1)
})
