import { describe, expect, test, vi } from 'vitest'

import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import {
  GenerativeAIWorkspaceSettingsType,
  IntegrationsWorkspaceSettingsType,
  SnapshotsWorkspaceSettingsType,
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

describe('SnapshotsWorkspaceSettingsType', () => {
  test('is only shown to users who can read the snapshot settings', () => {
    const hasPermission = vi.fn().mockReturnValue(false)
    const settingsType = new SnapshotsWorkspaceSettingsType({
      app: { $i18n: { t: (key) => key }, $hasPermission: hasPermission },
    })
    const workspace = { id: 42 }

    expect(settingsType.isEnabled(workspace)).toBe(false)
    expect(hasPermission).toHaveBeenCalledWith(
      'workspace.read_snapshot_settings',
      workspace,
      workspace.id
    )

    hasPermission.mockReturnValue(true)
    expect(settingsType.isEnabled(workspace)).toBe(true)
  })
})

describe('IntegrationsWorkspaceSettingsType', () => {
  test('is available to members who can list workspace integrations', () => {
    const hasPermission = vi.fn().mockReturnValue(true)
    const settingsType = new IntegrationsWorkspaceSettingsType({
      app: { $i18n: { t: (key) => key }, $hasPermission: hasPermission },
    })
    const workspace = { id: 42 }
    expect(settingsType.isEnabled(workspace)).toBe(true)
    expect(hasPermission).toHaveBeenCalledWith(
      'workspace.list_integrations',
      workspace,
      42
    )
    hasPermission.mockReturnValue(false)
    expect(settingsType.isEnabled(workspace)).toBe(false)
  })
})
