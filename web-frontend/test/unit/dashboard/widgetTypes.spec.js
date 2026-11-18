import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import { TestApp } from '@baserow/test/helpers/testApp'

import {
  TextFilterWidgetType,
  SummaryWidgetType,
} from '@baserow/modules/dashboard/widgetTypes'

const app = {
  $i18n: {
    t: (key) => key,
  },
}

describe('SummaryWidgetType', () => {
  const widget = { data_source_id: 42 }
  const widgetType = new SummaryWidgetType({ app })

  test('owns data-source loading and configuration state', () => {
    expect(widgetType.isLoading(widget, {})).toBe(true)
    expect(widgetType.isLoading(widget, { 42: { result: 1 } })).toBe(false)
    expect(widgetType.isMisconfigured(widget, { 42: { _error: true } })).toBe(
      true
    )
  })

  test('owns its header presentation', () => {
    expect(widgetType.showHeaderBorder).toBe(false)
  })
})

describe('a summary created for a table', () => {
  let testApp
  beforeEach(() => {
    testApp = new TestApp()
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  const summaryType = () =>
    testApp.getRegistry().get('dashboardWidget', 'summary')

  test('shows the first field, like choosing the table in its settings', () => {
    const fields = [
      { id: 7, type: 'number', name: 'Amount', primary: true },
      { id: 8, type: 'text', name: 'Notes' },
    ]
    const values = summaryType().getDataSourceValuesForTable(6, fields)
    const firstAggregation = testApp
      .getRegistry()
      .getOrderedList('viewAggregation')
      .find(
        (type) =>
          type.getType() !== 'distribution' && type.fieldIsCompatible(fields[0])
      )
    expect(values).toEqual({
      table_id: 6,
      field_id: 7,
      aggregation_type: firstAggregation.getType(),
    })
  })

  test('only shows the table when it has no field', () => {
    expect(summaryType().getDataSourceValuesForTable(6, [])).toEqual({
      table_id: 6,
    })
  })
})

test('filter refresh targets include only enabled links and support the public link graph', () => {
  const type = new TextFilterWidgetType({ app })
  expect(
    type.getTargetWidgetIds({
      target_filters: [
        { target_widget_id: 1 },
        { target_widget_id: 2, enabled: true },
        { target_widget_id: 3, enabled: false },
      ],
    })
  ).toEqual([1, 2])
  expect(type.getTargetWidgetIds({ target_widget_ids: [1, 2] })).toEqual([1, 2])
})

test.each([false, true])(
  'filter creation follows its feature flag (%s)',
  (enabled) => {
    const featureApp = {
      ...app,
      $featureFlagIsEnabled: (flag) => flag === 'dashboard-filters' && enabled,
    }
    const filter = new TextFilterWidgetType({ app: featureApp })
    const summary = new SummaryWidgetType({ app: featureApp })
    expect(filter.variations.map(({ type }) => type.getType())).toEqual(
      enabled ? ['text_filter'] : []
    )
    expect(summary.variations.map(({ type }) => type.getType())).toEqual([
      'summary',
    ])
    expect(filter.component).toBeDefined()
  }
)
