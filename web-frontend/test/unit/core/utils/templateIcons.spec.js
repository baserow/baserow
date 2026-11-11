import { describe, expect, test } from 'vitest'

import {
  DEFAULT_TEMPLATE_ICON,
  TEMPLATE_ICONS,
} from '@baserow/modules/core/utils/templateIcons'

describe('templateIcons', () => {
  test('only lists icons the backend accepts', () => {
    // Mirrors `USER_TEMPLATE_ICON_REGEX` and `USER_TEMPLATE_ICON_MAX_LENGTH`.
    for (const icon of TEMPLATE_ICONS) {
      expect(icon).toMatch(/^iconoir-[a-z0-9]+(-[a-z0-9]+)*$/)
      expect(icon.length).toBeLessThanOrEqual(32)
    }
    expect(new Set(TEMPLATE_ICONS).size).toBe(TEMPLATE_ICONS.length)
    expect(TEMPLATE_ICONS).toContain(DEFAULT_TEMPLATE_ICON)
  })
})
