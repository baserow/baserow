import { describe, expect, test, vi } from 'vitest'

import { GenerativeAIWorkspaceSettingsType } from '@baserow/modules/core/workspaceSettingsTypes'

function makeType(featureEnabled) {
  return new GenerativeAIWorkspaceSettingsType({
    app: {
      $i18n: { t: (key) => key },
      $featureFlagIsEnabled: vi.fn().mockReturnValue(featureEnabled),
    },
  })
}

describe('GenerativeAIWorkspaceSettingsType', () => {
  test('uses the AI provider name and icon with database providers enabled', () => {
    const settingsType = makeType(true)

    expect(settingsType.getName()).toBe('workspaceSettingType.aiProviders')
    expect(settingsType.getIconClass()).toBe('iconoir-sparks')
  })

  test('keeps the legacy generative AI name and icon otherwise', () => {
    const settingsType = makeType(false)

    expect(settingsType.getName()).toBe('workspaceSettingType.generativeAI')
    expect(settingsType.getIconClass()).toBe('iconoir-magic-wand')
  })
})
