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

const emptyGroup = { filter_type: 'AND', filters: [], filter_groups: [] }
const linkTo30 = {
  target_widget_id: 30,
  enabled: true,
  empty_behavior: 'apply_nothing',
  group: emptyGroup,
}

async function mountConfiguration({ linked = true, tableId = 5 } = {}) {
  const state = {
    widgets: [
      { id: 30, type: 'summary', title: 'Summary', data_source_id: 31 },
      {
        id: 2,
        type: 'text_filter',
        title: 'Region',
        target_filters: linked ? [linkTo30] : [],
      },
    ],
  }
  const actions = {
    updateWidget: vi.fn((_, { work }) => work),
    updateDataSource: (_, { work }) => work,
    deleteWidget: vi.fn(),
  }
  testApp.store.registerModule('guideddashboardApplication', {
    namespaced: true,
    state,
    getters: {
      getWidgets: (state) => state.widgets,
      getDataSourceById: () => (id) =>
        id === 31 ? { id: 31, table_id: tableId, integration_id: 10 } : null,
      getIntegrationById: () => (id) =>
        id === 10
          ? {
              id: 10,
              context_data: {
                databases: [{ id: 1, tables: [{ id: 5, name: 'Projects' }] }],
              },
            }
          : null,
    },
    actions,
  })
  const wrapper = await testApp.mount(ConfigureFilterTargetModal, {
    props: {
      dashboard: { id: 1 },
      widgetId: 30,
      linkFilterWidgetId: 2,
      storePrefix: 'guided',
    },
    global: {
      stubs: {
        Modal: {
          template: '<div><slot /></div>',
          emits: ['hidden'],
          methods: {
            show() {},
            hide() {
              this.$emit('hidden')
            },
          },
        },
        WidgetSettings: {
          name: 'WidgetSettings',
          template: '<div />',
          methods: { validate: () => validate() },
        },
        WidgetFilterConditions: {
          name: 'WidgetFilterConditions',
          props: ['link', 'widget', 'target'],
          template: '<div class="conditions-stub" />',
        },
      },
    },
  })
  return { wrapper, actions }
}
const button = (wrapper, label) =>
  wrapper.findAll('button').find((button) => button.text() === label)
const submitButton = (wrapper) =>
  button(wrapper, 'configureFilterTargetModal.add')

/** Control completion of an ordinary settings save without timing assumptions. */
function deferred() {
  let resolve, reject
  const work = new Promise((done, fail) => {
    resolve = done
    reject = fail
  })
  return { work, resolve, reject }
}

test('adds the widget only once its settings are valid and the filter links it', async () => {
  const { wrapper } = await mountConfiguration()
  validate.mockReturnValue(false)
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toBeUndefined()
  validate.mockReturnValue(true)
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')[0][0]).toMatchObject({ id: 30 })
})

test('hides the filter conditions until the widget shows a table', async () => {
  const { wrapper } = await mountConfiguration({ linked: false, tableId: null })
  expect(
    wrapper.find('.configure-filter-target__section--conditions').exists()
  ).toBe(false)
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toBeUndefined()
})

const sections = (wrapper) =>
  wrapper.findAll('.configure-filter-target__section-header')
const isOpen = (header) => header.attributes('aria-expanded') === 'true'

test('shows one section at a time, summing up the other', async () => {
  const { wrapper } = await mountConfiguration()
  const [widget, conditions] = sections(wrapper)
  expect([isOpen(widget), isOpen(conditions)]).toEqual([true, false])
  expect(conditions.text()).toContain(
    'configureFilterTargetModal.conditionsSummary'
  )
  await conditions.trigger('click')
  expect([isOpen(widget), isOpen(conditions)]).toEqual([false, true])
  expect(widget.text()).toContain('configureFilterTargetModal.widgetSummary')
  // Both stay mounted, so hidden settings still validate and save.
  expect(wrapper.find('.conditions-stub').exists()).toBe(true)
  expect(wrapper.findComponent({ name: 'WidgetSettings' }).exists()).toBe(true)
})

test('reopens the widget settings when they are not valid', async () => {
  const { wrapper } = await mountConfiguration()
  await sections(wrapper)[1].trigger('click')
  validate.mockReturnValue(false)
  await submitButton(wrapper).trigger('click')
  await flushPromises()
  expect(isOpen(sections(wrapper)[0])).toBe(true)
  expect(wrapper.emitted('configured')).toBeUndefined()
})

test('shows and saves how the filter narrows down the new widget', async () => {
  const { wrapper, actions } = await mountConfiguration()
  const conditions = wrapper.findComponent({ name: 'WidgetFilterConditions' })
  expect(conditions.props('link')).toEqual(linkTo30)
  expect(conditions.props('widget')).toMatchObject({ id: 2 })
  expect(conditions.props('target')).toMatchObject({ id: 30 })

  const edited = { ...linkTo30, empty_behavior: 'apply_alternative' }
  conditions.vm.$emit('update', edited)
  await flushPromises()

  const [, payload] = actions.updateWidget.mock.calls[0]
  expect(payload.widgetId).toBe(2)
  expect(payload.values.target_filters).toEqual([
    { ...edited, alternative_group: emptyGroup },
  ])
  expect(payload.originalValues.target_filters).toEqual([linkTo30])
})

test.each([
  ['cancelling', false, 1],
  ['adding, then closing', true, 0],
])('%s removes the new widget %i time(s)', async (_, add, deletions) => {
  const { wrapper, actions } = await mountConfiguration()
  if (add) await submitButton(wrapper).trigger('click')
  await button(wrapper, 'action.cancel').trigger('click')
  await flushPromises()
  expect(actions.deleteWidget).toHaveBeenCalledTimes(deletions)
  if (deletions) {
    expect(actions.deleteWidget.mock.calls[0][1]).toBe(30)
  }
  expect(wrapper.emitted('hidden')).toHaveLength(1)
})

test('waits for every pending save of the widget and its filter', async () => {
  const { wrapper } = await mountConfiguration()
  const title = deferred()
  const source = deferred()
  const filter = deferred()
  const saves = [
    testApp.store.dispatch('guideddashboardApplication/updateWidget', {
      widgetId: 30,
      work: title.work,
    }),
    testApp.store.dispatch('guideddashboardApplication/updateDataSource', {
      dataSourceId: 31,
      work: source.work,
    }),
    testApp.store.dispatch('guideddashboardApplication/updateWidget', {
      widgetId: 2,
      work: filter.work,
    }),
  ]
  for (const save of [title, source, filter]) {
    await flushPromises()
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    save.resolve()
  }
  await Promise.all(saves)
  await flushPromises()
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toHaveLength(1)
})

test('keeps failed saves visible until that setting is saved successfully', async () => {
  const { wrapper } = await mountConfiguration()
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
  expect(wrapper.text()).toContain('configureFilterTargetModal.saveFailed')
  expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
  await testApp.store.dispatch('guideddashboardApplication/updateDataSource', {
    dataSourceId: 31,
    work: Promise.resolve(),
  })
  await flushPromises()
  expect(wrapper.text()).not.toContain('configureFilterTargetModal.saveFailed')
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toHaveLength(1)
})

test('ignores saves for other widgets', async () => {
  const { wrapper } = await mountConfiguration()
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

test('uses the real summary settings, linking the widget when its table is chosen', async () => {
  const widget = {
    id: 30,
    type: 'summary',
    title: 'Summary',
    description: '',
    data_source_id: 31,
  }
  testApp.store.commit('dashboardApplication/SET_WIDGETS', [
    widget,
    { id: 2, type: 'text_filter', title: 'Region', target_filters: [] },
  ])
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
    props: { dashboard: { id: 1 }, widgetId: 30, linkFilterWidgetId: 2 },
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
      linkFilterWidgetId: 2,
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
  // The server links the widget to the filter that asked, as it shows a table.
  testApp.store.commit('dashboardApplication/UPDATE_WIDGET', {
    widgetId: 2,
    values: { target_filters: [linkTo30] },
  })
  await flushPromises()
  // The filter's conditions are set below: the widget's own aren't shown.
  expect(wrapper.find('.service-form__filter-buttons').exists()).toBe(false)
  expect(wrapper.find('.service-form__condition-form-tab').exists()).toBe(false)
  await submitButton(wrapper).trigger('click')
  expect(wrapper.emitted('configured')).toHaveLength(1)
})
