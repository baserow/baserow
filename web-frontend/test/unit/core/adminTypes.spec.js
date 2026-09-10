import { describe, expect, test } from 'vitest'

import { AIProvidersAdminType } from '@baserow/modules/core/adminTypes'

describe('AIProvidersAdminType', () => {
  test('is visible without an AI providers feature flag', () => {
    const adminType = new AIProvidersAdminType({
      app: { $i18n: { t: (key) => key } },
    })

    expect(adminType.isVisible()).toBe(true)
    expect(adminType.getRouteName()).toBe('admin-ai-providers')
  })
})
