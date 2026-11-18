import { describe, expect, test } from 'vitest'

import ChartWidget from '@baserow_premium/dashboard/components/widget/ChartWidget'
import {
  ChartWidgetType,
  PieChartWidgetType,
} from '@baserow_premium/dashboard/widgetTypes'

const app = {
  $i18n: {
    t: (key) => key,
  },
}

describe('premium dashboard widget types', () => {
  test('maps cartesian and pie widgets to the shared chart component', () => {
    expect(new ChartWidgetType({ app }).component).toBe(ChartWidget)
    expect(new PieChartWidgetType({ app }).component).toBe(ChartWidget)
  })

  test('a chart created for a table starts with one series to fill in', () => {
    // Like choosing the table in the settings, which expect a series to exist.
    for (const Type of [ChartWidgetType, PieChartWidgetType]) {
      expect(new Type({ app }).getDataSourceValuesForTable(6)).toEqual({
        table_id: 6,
        aggregation_series: [{ field_id: null, aggregation_type: '' }],
      })
    }
  })
})
