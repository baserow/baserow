import { TestApp } from '@baserow/test/helpers/testApp'
import SummaryWidget from '@baserow/modules/dashboard/components/widget/SummaryWidget'

describe('dashboard source dispatch', () => {
  let testApp, store, mock, savedFilter
  const source = {
    id: 10,
    dashboard_id: 1,
    type: 'local_baserow_aggregate_rows',
    aggregation_type: 'count',
    context_data: { field: { type: 'text' } },
    filters: [
      {
        field: 1,
        type: 'equal',
        value: { formula: "get('dashboard_filter.5')", mode: 'simple' },
      },
    ],
  }
  const widgets = [2, 3].map((id) => ({
    id,
    dashboard_id: 1,
    type: 'summary',
    data_source_id: source.id,
  }))
  const filter = {
    id: 5,
    dashboard_id: 1,
    type: 'text',
    label: 'Country',
    mode: 'input',
    multiple: false,
    operator: 'equal',
  }

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    mock = testApp.mock
    mock.onGet('/dashboard/1/widgets/').reply(200, widgets)
    savedFilter = { ...filter, values: [] }
    mock.onGet('/dashboard/1/filters/').reply(() => [200, [savedFilter]])
    mock.onPatch('/dashboard/filters/5/').reply(({ data }) => {
      savedFilter = { ...savedFilter, ...JSON.parse(data) }
      return [200, savedFilter]
    })
    mock.onGet('/dashboard/1/data-sources/').reply(200, [source])
    mock
      .onPost('/dashboard/data-sources/10/dispatch/')
      .reply(() => [200, { result: savedFilter.values.length ? 12 : 42 }])
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('dispatches a shared source once and updates every widget with its filter values', async () => {
    await store.dispatch('dashboardApplication/fetchInitial', {
      dashboardId: 1,
      forEditing: false,
    })
    const wrappers = await Promise.all(
      widgets.map((widget) =>
        testApp.mount(SummaryWidget, { props: { widget } })
      )
    )
    expect(mock.history.post).toHaveLength(1)
    expect(wrappers.map((wrapper) => wrapper.text())).toEqual(['42', '42'])

    await store.dispatch('dashboardApplication/applyFilter', {
      filterId: filter.id,
      values: ['France'],
    })
    expect(mock.history.post).toHaveLength(2)
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({
      values: ['France'],
    })
    expect(JSON.parse(mock.history.post[1].data)).toEqual({})
    expect(wrappers.map((wrapper) => wrapper.text())).toEqual(['12', '12'])

    const newWidget = { ...widgets[0], id: 4 }
    await store.dispatch(
      'dashboardApplication/handleNewWidgetCreated',
      newWidget
    )
    await store.dispatch('dashboardApplication/fetchNewDataSources', 1)
    const wrapper = await testApp.mount(SummaryWidget, {
      props: { widget: newWidget },
    })
    expect(wrapper.text()).toBe('12')
    expect(mock.history.post).toHaveLength(2)
  })
})
