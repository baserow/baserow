import { describe, expect, test, vi } from 'vitest'

import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import InvitationLinksTable from '@baserow/modules/core/components/settings/invitationLinks/InvitationLinksTable'
import {
  GenerativeAIWorkspaceSettingsType,
  InvitationLinksWorkspaceSettingsType,
} from '@baserow/modules/core/workspaceSettingsTypes'

describe('GenerativeAIWorkspaceSettingsType', () => {
  test('opens AI provider management', () => {
    const settingsType = new GenerativeAIWorkspaceSettingsType({
      app: { $i18n: { t: (key) => key } },
    })

    expect(settingsType.getName()).toBe('workspaceSettingType.aiProviders')
    expect(settingsType.getIconClass()).toBe('iconoir-sparks')
    expect(settingsType.getComponent()).toBe(AIProviderWorkspaceSettings)
  })
})

describe('InvitationLinksWorkspaceSettingsType', () => {
  function createSettingsType({ featureFlag = true, canManage = [] } = {}) {
    const targetTypes = canManage.map((value) => ({
      canManageInvitationLinks: vi.fn().mockReturnValue(value),
    }))
    return new InvitationLinksWorkspaceSettingsType({
      app: {
        $i18n: { t: (key) => key },
        $featureFlagIsEnabled: () => featureFlag,
        $registry: { getAll: () => ({ ...targetTypes }) },
      },
    })
  }

  test('opens the invitation links of the workspace', () => {
    const settingsType = createSettingsType()

    expect(settingsType.getName()).toBe('invitationLinksSettings.tabTitle')
    expect(settingsType.getIconClass()).toBe('iconoir-link')
    expect(settingsType.getComponent()).toBe(InvitationLinksTable)
  })

  test.each([
    [{ canManage: [false, true] }, true],
    [{ canManage: [false, false] }, false],
    [{ canManage: [] }, false],
    [{ canManage: [true], featureFlag: false }, false],
  ])('with %o it is enabled: %s', (options, expected) => {
    expect(createSettingsType(options).isEnabled({ id: 1 })).toBe(expected)
  })
})
