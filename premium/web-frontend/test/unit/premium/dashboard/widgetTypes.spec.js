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
})
