import { describe, expect, test, vi } from 'vitest'

import { AIProvidersAdminType } from '@baserow/modules/core/adminTypes'

describe('AIProvidersAdminType', () => {
  test('is only visible while its feature flag is enabled', () => {
    const featureFlagIsEnabled = vi.fn().mockReturnValue(false)
    const adminType = new AIProvidersAdminType({
      app: {
        $i18n: { t: (key) => key },
        $featureFlagIsEnabled: featureFlagIsEnabled,
      },
    })

    expect(adminType.isVisible()).toBe(false)
    expect(featureFlagIsEnabled).toHaveBeenCalledWith('ai-providers')
    featureFlagIsEnabled.mockReturnValue(true)
    expect(adminType.isVisible()).toBe(true)
  })
})
