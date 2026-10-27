import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import DashboardFilters from '@baserow/modules/dashboard/components/filter/DashboardFilters'

const { hasPermission } = vi.hoisted(() => ({ hasPermission: vi.fn() }))
vi.mock('#app', async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    useNuxtApp: (...args) =>
      new Proxy(original.useNuxtApp(...args), {
        get: (app, key) =>
          key === '$hasPermission' ? hasPermission : app[key],
      }),
  }
})

let testApp, store, mock, filters
const dashboard = { id: 1, workspace: { id: 1 } }
beforeEach(async () => {
  hasPermission.mockReturnValue(true)
  testApp = new TestApp()
  testApp.dontFailOnErrorResponses()
  ;({ store, mock } = testApp)
  filters = [5, 6].map((id) => ({
    id,
    dashboard_id: 1,
    label: `Filter ${id}`,
    type: 'text',
    operator: 'equal',
    mode: 'input',
    multiple: false,
    values: [`Old ${id}`],
  }))
  const sources = filters.map(({ id }) => ({
    id: id * 10,
    dashboard_id: 1,
    type: 'local_baserow_aggregate_rows',
    aggregation_type: 'count',
    filters: [
      {
        field: 1,
        type: 'equal',
        value: { formula: `get('dashboard_filter.${id}')`, mode: 'simple' },
      },
    ],
  }))
  mock.onGet('/dashboard/1/widgets/').reply(200, [])
  mock
    .onGet('/dashboard/1/filters/')
    .reply(() => [200, structuredClone(filters)])
  mock.onGet('/dashboard/1/data-sources/').reply(200, sources)
  for (const id of [5, 6]) {
    mock.onPatch(`/dashboard/filters/${id}/`).reply(({ data }) => {
      filters = filters.map((filter) =>
        filter.id === id ? { ...filter, ...JSON.parse(data) } : filter
      )
      return [200, filters.find((filter) => filter.id === id)]
    })
    mock.onPost(`/dashboard/data-sources/${id * 10}/dispatch/`).reply(() => [
      200,
      {
        result: filters.find((filter) => filter.id === id).values[0],
      },
    ])
  }
  await store.dispatch('dashboardApplication/fetchInitial', {
    dashboardId: 1,
    forEditing: false,
  })
})
afterEach(async () => {
  await testApp.afterEach()
})

test('concurrent saves wait for synchronization and preserve the open draft on failure', async () => {
  const wrapper = await testApp.mount(DashboardFilters, {
    global: { stubs: { Teleport: false } },
    props: { dashboard },
  })
  const reads = []
  mock.onGet('/dashboard/1/filters/').reply(() => {
    const snapshot = structuredClone(filters)
    return new Promise((resolve) => reads.push({ snapshot, resolve }))
  })
  mock.resetHistory()
  for (let index = 0; index < 2; index++) {
    await wrapper.findAll('.dropdown__selected')[index].trigger('click')
    await flushPromises()
    const forms = testApp.body.findAll('form:has(.dashboard-filter__input)')
    const form = forms[forms.length - 1]
    await form.get('input').setValue(`New ${index + 5}`)
    await form.trigger('submit')
    await flushPromises()
    expect(reads).toHaveLength(index + 1)
  }
  expect(mock.history.patch).toHaveLength(2)
  expect(filters.map(({ values }) => values)).toEqual([['New 5'], ['New 6']])
  reads[0].resolve([200, reads[0].snapshot])
  await flushPromises()
  expect(wrapper.findAll('.dropdown__selected')[0].element.disabled).toBe(true)
  expect(mock.history.post).toHaveLength(0)
  reads[1].resolve([500])
  await flushPromises()
  expect(wrapper.findAll('.dropdown__selected')[0].element.disabled).toBe(false)
  expect(
    wrapper.findAll('.dashboard-filter__value').map((value) => value.text())
  ).toEqual(['Old 5', 'Old 6'])
  const forms = testApp.body.findAll('form:has(.dashboard-filter__input)')
  expect(forms[1].get('input').element.value).toBe('New 6')
  expect(forms[1].get('button[type="submit"]').element.disabled).toBe(false)

  mock
    .onGet('/dashboard/1/filters/')
    .reply(() => [200, structuredClone(filters)])
  await forms[1].trigger('submit')
  await flushPromises()
  expect(
    wrapper.findAll('.dashboard-filter__value').map((value) => value.text())
  ).toEqual(['New 5', 'New 6'])
  expect(
    store.getters['dashboardApplication/getDataForDataSource'](50)
  ).toEqual({ result: 'New 5' })
  expect(
    store.getters['dashboardApplication/getDataForDataSource'](60)
  ).toEqual({ result: 'New 6' })
})

test.each([
  [200, 'first'],
  [200, 'latest'],
  [500, 'first'],
  [500, 'latest'],
])(
  'concurrent saves share the current read result (%s, %s response first)',
  async (status, first) => {
    const reads = []
    mock.onGet('/dashboard/1/filters/').reply(() => {
      const snapshot = structuredClone(filters)
      return new Promise((resolve) => reads.push({ snapshot, resolve }))
    })
    mock.resetHistory()
    const save = (filterId) =>
      store
        .dispatch('dashboardApplication/applyFilter', {
          filterId,
          values: [`New ${filterId}`],
        })
        .then(
          () => 'saved',
          () => 'failed'
        )
    const firstSave = save(5)
    await flushPromises()
    const latestSave = save(6)
    await flushPromises()
    expect(reads).toHaveLength(2)
    const finishFirst = () => reads[0].resolve([200, reads[0].snapshot])
    const finishLatest = () => reads[1].resolve([status, reads[1].snapshot])
    if (first === 'first') {
      finishFirst()
      await flushPromises()
      finishLatest()
    } else {
      finishLatest()
      await flushPromises()
      finishFirst()
    }
    expect(await Promise.all([firstSave, latestSave])).toEqual(
      status === 200 ? ['saved', 'saved'] : ['failed', 'failed']
    )
    expect(
      store.getters['dashboardApplication/getAppliedFilterValues'](5)
    ).toEqual(status === 200 ? ['New 5'] : ['Old 5'])
    expect(
      store.getters['dashboardApplication/getDataForDataSource'](50)
    ).toEqual({
      result: status === 200 ? 'New 5' : 'Old 5',
    })
    expect(reads).toHaveLength(2)
  }
)
