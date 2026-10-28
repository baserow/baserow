import { describe, expect, test } from 'vitest'

import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import { GenerativeAIWorkspaceSettingsType } from '@baserow/modules/core/workspaceSettingsTypes'
import { unwrapLazyComponent } from '@baserow/modules/core/utils/lazyComponent'

describe('GenerativeAIWorkspaceSettingsType', () => {
  test('opens AI provider management', () => {
    const settingsType = new GenerativeAIWorkspaceSettingsType({
      app: { $i18n: { t: (key) => key } },
    })

    expect(settingsType.getName()).toBe('workspaceSettingType.aiProviders')
    expect(settingsType.getIconClass()).toBe('iconoir-sparks')
    expect(unwrapLazyComponent(settingsType.getComponent())).toBe(
      AIProviderWorkspaceSettings
    )
  })
})
