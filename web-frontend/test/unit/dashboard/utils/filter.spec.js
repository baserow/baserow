import {
  filterHasOptions,
  filterHasValue,
  getDataSourceFilterInputs,
  getReferencedDashboardFilterId,
  hasActiveDashboardFilter,
  shouldResetFilterValues,
} from '@baserow/modules/dashboard/utils/filter'
import { Registry } from '@baserow/modules/core/registry'
import { ServiceType } from '@baserow/modules/core/serviceTypes'
import { LocalBaserowAggregateRowsServiceType } from '@baserow/modules/integrations/localBaserow/serviceTypes'

describe('data source filter dispatch inputs', () => {
  const serviceType = new LocalBaserowAggregateRowsServiceType()
  const filters = [12, 13].map((id) => ({
    id,
    type: 'text',
    operator: 'equal',
    mode: 'input',
    multiple: false,
    values: [],
  }))
  const source = (formula, mode = 'simple') => ({
    type: 'local_baserow_aggregate_rows',
    filters: [{ field: 1, value: { formula, mode } }],
  })

  test.each([
    ["get('dashboard_filter.12')", [12]],
    ["upper(get('dashboard_filter[12][0]'))", [12]],
    [
      "concat(get('dashboard_filter.12.*'), get('dashboard_filter.13'))",
      [12, 13],
    ],
    ["get(concat('dashboard_filter.', '12'))", [12, 13]],
    ["get('dashboard_filter.12", [12, 13]],
    ["get('table.12')", []],
    ['"get(\'dashboard_filter.12\')"', []],
  ])(
    'captures references in %s even when selections are cleared',
    (formula, ids) => {
      expect(
        getDataSourceFilterInputs(
          source(formula),
          filters,
          serviceType
        ).filters.map(({ id }) => id)
      ).toEqual(ids)
    }
  )

  test('raw formulas and inactive conditions have no runtime dependency', () => {
    expect(
      getDataSourceFilterInputs(
        source("get('dashboard_filter.12')", 'raw'),
        filters,
        serviceType
      ).filters
    ).toEqual([])
    const dataSource = source("get('dashboard_filter.12')")
    dataSource.filters[0].trashed = true
    expect(
      getDataSourceFilterInputs(dataSource, filters, serviceType).filters
    ).toEqual([])
    delete dataSource.filters[0].trashed
    dataSource.filters[0].field = null
    expect(
      getDataSourceFilterInputs(dataSource, filters, serviceType).filters
    ).toEqual([])
  })

  test('search queries count as dependencies but context schema formulas do not', () => {
    const dataSource = source('literal', 'raw')
    dataSource.search_query = {
      formula: "upper(get('dashboard_filter.13'))",
      mode: 'simple',
    }
    dataSource.context_data = { formula: "get('dashboard_filter.12')" }
    expect(
      getDataSourceFilterInputs(dataSource, filters, serviceType).filters.map(
        ({ id }) => id
      )
    ).toEqual([13])
  })

  test('unsupported service types conservatively depend on all filters', () => {
    expect(
      getDataSourceFilterInputs(
        { type: 'future_service' },
        filters,
        new ServiceType()
      ).filters
    ).toHaveLength(2)
  })

  test('an unregistered source conservatively depends on all filters', () => {
    const dataSource = { type: 'missing_service', expression: 'unrecognized' }
    const inputs = getDataSourceFilterInputs(dataSource, filters)
    expect(inputs.filters).toHaveLength(2)
    expect(inputs.configuration).toEqual(dataSource)
  })

  test('a registered service can describe a different formula field', () => {
    class CustomServiceType extends ServiceType {
      static getType() {
        return 'custom_service'
      }

      getDispatchInputs(service) {
        return {
          configuration: { expression: service.expression },
          formulas: [service.expression],
        }
      }
    }
    const registry = new Registry()
    registry.registerNamespace('service')
    registry.register('service', new CustomServiceType())
    const dataSource = {
      type: 'custom_service',
      name: 'Display name',
      expression: {
        formula: "upper(get('dashboard_filter.13'))",
        mode: 'simple',
      },
    }
    const inputs = getDataSourceFilterInputs(
      dataSource,
      filters,
      registry.get('service', dataSource.type)
    )
    expect(inputs.configuration).toEqual({ expression: dataSource.expression })
    expect(inputs.filters.map(({ id }) => id)).toEqual([13])
  })

  test('a missing referenced filter is retained so deletion and restoration change inputs', () => {
    expect(
      getDataSourceFilterInputs(
        source("get('dashboard_filter.12')"),
        [],
        serviceType
      ).filters
    ).toEqual([{ id: 12 }])
  })
})

test.each([
  ["get('dashboard_filter.12')", 12],
  [' GET("dashboard_filter.12") ', 12],
  ["get( 'dashboard_filter.12' )", 12],
  ["get(('dashboard_filter.12'))", 12],
  ["(get('dashboard_filter.12'))", 12],
  ["get('dashboard_filter.12.*')", 12],
  ["get('dashboard_filter.12.1')", 12],
  ["get('dashboard_filter[12]')", 12],
  ["get('dashboard_filter.12[0]')", 12],
  ['get("dashboard_filter[\\"12\\"][\\"*\\"]")', null],
  ["get('dashboard_filter[ 12 ][ * ]')", 12],
  ["concat(get('dashboard_filter.12'), '')", null],
  ["get('dashboard_filter.12') + get('dashboard_filter.13')", null],
  ["get('table.12')", null],
  ["get('dashboard_filter.0')", null],
  ["get('dashboard_filter.12", null],
])(
  'identifies the control for %s without treating calculations as links',
  (formula, expected) => {
    expect(getReferencedDashboardFilterId({ formula, mode: 'simple' })).toBe(
      expected
    )
  }
)

test('literal text that looks like a control reference stays literal', () => {
  expect(
    getReferencedDashboardFilterId({
      formula: "get('dashboard_filter.12')",
      mode: 'raw',
    })
  ).toBeNull()
})

test.each([
  ["get('dashboard_filter.12')", ['France'], true],
  ["get('dashboard_filter[ 12 ][ * ]')", ['France'], true],
  ["get('dashboard_filter.12')", [], false],
  ["get('dashboard_filter.12')", ['  '], false],
  ["get('dashboard_filter.12.*')", ['France', 'Belgium'], true],
  ["get('dashboard_filter[12]')", ['France'], true],
  ["get('dashboard_filter.12[0]')", ['France'], true],
  ["get('dashboard_filter.12.1')", ['France'], false],
  ["get('dashboard_filter.12.1')", ['France', 'Belgium'], true],
  ["get('dashboard_filter.13')", ['France'], false],
  ["concat(get('dashboard_filter.12'), '')", ['France'], true],
  ["'dashboard_filter.12'", ['France'], false],
  ['"get(\'dashboard_filter.12\')"', ['France'], false],
  ["get('table.12')", ['France'], false],
  ["get('dashboard_filter.12", ['France'], false],
])(
  'detects an active dashboard filter in %s with %j',
  (formula, values, expected) => {
    expect(
      hasActiveDashboardFilter({ formula, mode: 'simple' }, [
        { id: 12, mode: 'dropdown', multiple: true, values },
      ])
    ).toBe(expected)
  }
)

test.each(['empty', 'not_empty', 'is_even_and_whole'])(
  'recognizes a %s condition only when activated',
  (operator) => {
    const formula = { formula: "get('dashboard_filter.12')", mode: 'simple' }
    const filter = { id: 12, mode: 'input', operator }
    expect(hasActiveDashboardFilter(formula, [{ ...filter, values: [] }])).toBe(
      false
    )
    expect(
      hasActiveDashboardFilter(formula, [{ ...filter, values: ['true'] }])
    ).toBe(true)
  }
)

test.each(['empty', 'not_empty', 'is_even_and_whole'])(
  'a %s filter needs neither an input value nor dropdown options',
  (operator) => {
    const filter = {
      type: 'number',
      operator,
      mode: 'dropdown',
      multiple: true,
    }
    expect(filterHasValue(filter)).toBe(false)
    expect(filterHasOptions(filter)).toBe(false)
  }
)

test.each([
  [
    { type: 'text', operator: 'equal' },
    { type: 'number', operator: 'equal' },
    true,
  ],
  [
    { type: 'number', operator: 'equal' },
    { type: 'date', operator: 'date_is' },
    true,
  ],
  [
    { type: 'date', operator: 'date_is' },
    { type: 'text', operator: 'equal' },
    true,
  ],
  [{ operator: 'equal' }, { type: 'text', operator: 'equal' }, false],
  [{ operator: 'equal' }, { type: 'number', operator: 'equal' }, true],
  [
    { type: 'number', operator: 'equal' },
    { type: 'number', operator: 'higher_than' },
    false,
  ],
  [
    { type: 'date', operator: 'date_is' },
    { type: 'date', operator: 'date_is_before' },
    false,
  ],
  [
    { type: 'date', operator: 'date_is' },
    { type: 'date', operator: 'contains' },
    true,
  ],
  [
    { type: 'date', operator: 'contains' },
    { type: 'date', operator: 'date_is' },
    true,
  ],
  [
    { type: 'date', operator: 'date_is' },
    { type: 'date', operator: 'date_is_within' },
    true,
  ],
  [
    { type: 'date', operator: 'date_is_within' },
    { type: 'date', operator: 'date_is' },
    true,
  ],
  [
    { type: 'date', operator: 'date_is' },
    { type: 'date', operator: 'date_equals_day_of_month' },
    true,
  ],
  [
    { type: 'date', operator: 'date_equals_day_of_month' },
    { type: 'date', operator: 'contains' },
    true,
  ],
])(
  'resets incompatible filter values from %j to %j: %s',
  (previous, next, resets) => {
    const defaults = { mode: 'input', multiple: false }
    expect(
      shouldResetFilterValues(
        { ...defaults, ...previous },
        { ...defaults, ...next }
      )
    ).toBe(resets)
  }
)

test('ignores a removed control and raw text', () => {
  const formula = { formula: "get('dashboard_filter.12')", mode: 'simple' }
  expect(hasActiveDashboardFilter(formula, [])).toBe(false)
  expect(
    hasActiveDashboardFilter({ ...formula, mode: 'raw' }, [
      { id: 12, mode: 'input', values: ['France'] },
    ])
  ).toBe(false)
})

test.each(['input', 'dropdown'])(
  'keeps indexed references active after switching to a single %s value',
  (mode) => {
    const filter = { id: 12, mode, multiple: false }
    for (const suffix of ['', '.*', '.0', '[0]']) {
      expect(
        hasActiveDashboardFilter(
          { formula: `get('dashboard_filter.12${suffix}')`, mode: 'simple' },
          [{ ...filter, values: ['France'] }]
        )
      ).toBe(true)
    }
    expect(
      hasActiveDashboardFilter(
        { formula: "get('dashboard_filter.12.1')", mode: 'simple' },
        [{ ...filter, values: ['France', 'Belgium'] }]
      )
    ).toBe(false)
  }
)
