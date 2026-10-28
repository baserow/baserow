import { describe, expect, test } from 'vitest'

import ChartWidget from '@baserow_premium/dashboard/components/widget/ChartWidget'
import {
  ChartWidgetType,
  PieChartWidgetType,
} from '@baserow_premium/dashboard/widgetTypes'
import { unwrapLazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const app = {
  $i18n: {
    t: (key) => key,
  },
}

describe('premium dashboard widget types', () => {
  test('maps cartesian and pie widgets to the shared chart component', () => {
    expect(unwrapLazyComponent(new ChartWidgetType({ app }).component)).toBe(
      ChartWidget
    )
    expect(unwrapLazyComponent(new PieChartWidgetType({ app }).component)).toBe(
      ChartWidget
    )
  })
})
