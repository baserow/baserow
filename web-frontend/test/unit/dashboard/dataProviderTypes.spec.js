import { TestApp } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'
import DashboardFormulaInput from '@baserow/modules/dashboard/components/DashboardFormulaInput'
import { isFormulaValid } from '@baserow/modules/core/formula'
import { RuntimeFunctionCollection } from '@baserow/modules/core/functionCollection'

let testApp
beforeEach(() => {
  testApp = new TestApp()
  testApp.store.commit('dashboardApplication/SET_FILTERS', [
    { id: 1, label: 'Country', mode: 'input', values: ['France'] },
    {
      id: 2,
      label: 'Teams',
      mode: 'dropdown',
      multiple: true,
      values: ['Design', 'Marketing'],
    },
  ])
})
afterEach(() => testApp.afterEach())

test('exposes scalar and list values with readable names', () => {
  const provider = testApp.nuxtApp.$registry.get(
    'dashboardDataProvider',
    'dashboard_filter'
  )
  expect(provider.getDataChunk({}, ['1'])).toBe('France')
  expect(provider.getDataChunk({}, ['2'])).toEqual(['Design', 'Marketing'])
  expect(provider.getDataChunk({}, ['2', '1'])).toBe('Marketing')
  expect(
    provider.getNodes({}).nodes.map(({ name, type }) => ({ name, type }))
  ).toEqual([
    { name: 'Country', type: 'string' },
    { name: 'Teams', type: 'array' },
  ])
  expect(provider.getDataContent({ storePrefix: 'template/' })).toEqual({})
})

test('renders a dashboard filter reference in the shared formula input', async () => {
  const wrapper = await testApp.mount(DashboardFormulaInput, {
    props: {
      modelValue: { formula: "get('dashboard_filter.1')", mode: 'advanced' },
      dataProvidersAllowed: ['dashboard_filter'],
    },
    global: { provide: { dashboardApplicationContext: { storePrefix: '' } } },
  })
  expect(wrapper.get('.get-formula-component').text()).toContain('Country')
  expect(wrapper.find('.formula-input-field--error').exists()).toBe(false)
})

test('preserves the default formula path validation for other consumers', () => {
  const result = isFormulaValid(
    "get('dashboard_filter[2]')",
    new RuntimeFunctionCollection(testApp.store.$registry),
    false,
    {
      dataProviderRegistry: [
        testApp.nuxtApp.$registry.get(
          'dashboardDataProvider',
          'dashboard_filter'
        ),
      ],
    }
  )
  expect(result.valid).toBe(false)
})

test.each([
  ["get('dashboard_filter[2]')", true],
  ["get('dashboard_filter[ 2 ][ * ]')", true],
  ["get('dashboard_filter.2[ 0 ]')", true],
  ['get(\'dashboard_filter["2"]["*"]\')', false],
])(
  'validates and renders %s using the backend path rules',
  async (formula, valid) => {
    const wrapper = await testApp.mount(DashboardFormulaInput, {
      props: {
        modelValue: { formula, mode: 'advanced' },
        dataProvidersAllowed: ['dashboard_filter'],
      },
      global: { provide: { dashboardApplicationContext: { storePrefix: '' } } },
    })
    expect(wrapper.find('.get-formula-component--error').exists()).toBe(!valid)
    expect(wrapper.find('.formula-input-field--error').exists()).toBe(!valid)
    if (valid)
      expect(wrapper.get('.get-formula-component').text()).toContain('Teams')
  }
)

test.each([
  ['input', '*'],
  ['input', '0'],
  ['dropdown', '*'],
  ['dropdown', '0'],
])(
  'keeps existing indexed links usable after changing to a single %s value (%s)',
  async (mode, selector) => {
    const provider = testApp.nuxtApp.$registry.get(
      'dashboardDataProvider',
      'dashboard_filter'
    )
    const wrapper = await testApp.mount(DashboardFormulaInput, {
      props: {
        modelValue: {
          formula: `get('dashboard_filter.2.${selector}')`,
          mode: 'advanced',
        },
        dataProvidersAllowed: ['dashboard_filter'],
      },
      global: { provide: { dashboardApplicationContext: { storePrefix: '' } } },
    })
    testApp.store.commit('dashboardApplication/SET_FILTERS', [
      { id: 2, label: 'Teams', mode, multiple: false, values: [] },
    ])
    expect(provider.getDataChunk({}, ['2', '*'])).toEqual([])
    testApp.store.commit('dashboardApplication/SET_FILTERS', [
      { id: 2, label: 'Teams', mode, multiple: false, values: ['Design'] },
    ])
    await flushPromises()

    expect(provider.getDataChunk({}, ['2'])).toBe('Design')
    expect(provider.getDataChunk({}, ['2', '*'])).toEqual(['Design'])
    expect(provider.getDataChunk({}, ['2', '0'])).toBe('Design')
    expect(provider.getDataChunk({}, ['2', '1'])).toBeNull()
    expect(wrapper.get('.get-formula-component').text()).toContain('Teams')
    expect(wrapper.find('.get-formula-component--error').exists()).toBe(false)
    expect(provider.getNodes({}).nodes[0].nodes).toBeUndefined()

    await wrapper.setProps({
      modelValue: {
        formula: "get('dashboard_filter.2.*.0')",
        mode: 'advanced',
      },
    })
    await flushPromises()
    expect(wrapper.find('.get-formula-component--error').exists()).toBe(true)
  }
)

test.each([
  ['dashboard_filter', ['nope']],
  ['dashboard_filter', ['0']],
  ['dashboard_filter', ['1', 'extra']],
  ['table', ['nope']],
  ['table', ['1', 'result']],
  ['table', ['1', '*', 'field_0']],
])('rejects invalid %s paths', (type, path) => {
  expect(
    testApp.nuxtApp.$registry.get('dashboardDataProvider', type).isValid(path)
  ).toBe(false)
})

test('explores each widget table once, including fields unused by its aggregation', () => {
  const store = testApp.store
  const schema = {
    title: 'Orders',
    type: 'array',
    items: {
      type: 'object',
      properties: {
        field_11: { type: 'string', title: 'Country' },
        field_12: { type: 'number', title: 'Amount' },
      },
    },
  }
  store.commit('dashboardApplication/SET_WIDGETS', [
    { id: 1, data_source_id: 21 },
    { id: 2, data_source_id: 22 },
  ])
  store.commit('dashboardApplication/SET_DATA_SOURCES', [
    { id: 21, table_id: 10, table_schema: schema },
    { id: 22, table_id: 10, table_schema: schema },
    { id: 23, table_id: 20, table_schema: { ...schema, title: 'Unused' } },
  ])
  const provider = testApp.nuxtApp.$registry.get(
    'dashboardDataProvider',
    'table'
  )
  expect(provider.getDataSchema({})).toEqual({
    type: 'object',
    properties: { 10: { ...schema, order: 0 } },
  })
  expect(
    provider.getDataSchema({ storePrefix: 'template/' }).properties
  ).toEqual({})
})
