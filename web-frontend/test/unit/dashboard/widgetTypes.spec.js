import { describe, expect, test } from 'vitest'

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
