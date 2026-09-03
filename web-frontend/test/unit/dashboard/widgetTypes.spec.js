import { describe, expect, test } from 'vitest'

import { SummaryWidgetType } from '@baserow/modules/dashboard/widgetTypes'

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
